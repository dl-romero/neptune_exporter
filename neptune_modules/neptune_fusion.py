"""Neptune Fusion web-scrape API module."""

import datetime
import json
import logging
from pathlib import Path

import yaml
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "configuration" / "fusion.yml"
LOG_DIR.mkdir(exist_ok=True)


def setup_logger(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with the specified name, log file, and log level."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(handler)
    return logger


application_logger = setup_logger("neptune_fusion", LOG_DIR / "neptune.log")


def load_configuration() -> dict:
    """Load the Fusion configuration from disk safely."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            loaded_config = yaml.safe_load(config_file) or {}
    except FileNotFoundError as exc:
        raise RuntimeError(f"Fusion configuration file not found: {CONFIG_PATH}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in Fusion configuration: {CONFIG_PATH}") from exc

    if not isinstance(loaded_config, dict):
        raise RuntimeError("Fusion configuration must be a dictionary.")

    return loaded_config


try:
    configuration = load_configuration()
except RuntimeError as exc:
    application_logger.exception("Configuration File Load Failed: %s", exc)
    raise SystemExit(1) from exc


class FUSION:
    """Web-scraping client for the Neptune Fusion APIs."""

    def __init__(self, fusion_apex_id, max_data_age, fusion_debug=False):
        self.fusion_debug = fusion_debug
        self.fusion_apex_id = str(fusion_apex_id)
        self.max_data_age = int(max_data_age) + 60
        self.driver = None

        credentials = configuration.get("fusion", {}).get("apex_systems", {}).get(self.fusion_apex_id)
        if not credentials:
            raise ValueError(f"Unknown Fusion Apex ID: {self.fusion_apex_id}")

        chrome_options = Options()
        for option in (
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ):
            chrome_options.add_argument(option)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.fusion_login(credentials["username"], credentials["password"])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the Selenium session cleanly."""
        if self.driver is not None:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
            finally:
                self.driver = None

    def fusion_login(self, username, password):
        """Log into Fusion."""
        try:
            self.driver.get("https://apexfusion.com/login")
            id_box = WebDriverWait(self.driver, 30).until(
                expected_conditions.presence_of_element_located((By.ID, "index-login-username"))
            )
            id_box.send_keys(str(username))
            pass_box = self.driver.find_element(By.ID, "index-login-password")
            pass_box.send_keys(str(password))
            self.driver.find_element(By.CLASS_NAME, "af-sign-in").click()
            self.driver.implicitly_wait(3)
        except (TimeoutException, WebDriverException) as exc:
            application_logger.error("Fusion login failed: %s", exc)
            self.close()
            raise RuntimeError("Unable to authenticate with Neptune Fusion.") from exc

    def page_pre_to_json(self):
        """Extract JSON payloads embedded in pre tags."""
        html_content = str(self.driver.page_source)
        start = html_content.find("<pre>")
        end = html_content.find("</pre>")
        if start == -1 or end == -1:
            raise RuntimeError("Fusion response did not contain a JSON payload.")

        payload = html_content[start + len("<pre>"):end]
        return json.loads(payload)

    def get_measurement_log(self):
        """Get the measurement log from Fusion."""
        if self.fusion_debug:
            mlog_url = f"https://apexfusion.com/api/apex/{self.fusion_apex_id}/mlog?days=365"
        else:
            mlog_url = f"https://apexfusion.com/api/apex/{self.fusion_apex_id}/mlog?days=1"

        self.driver.get(mlog_url)
        self.driver.implicitly_wait(3)
        self.driver.refresh()
        self.driver.implicitly_wait(3)

        try:
            return self.page_pre_to_json()
        except (RuntimeError, json.JSONDecodeError):
            self.driver.refresh()
            self.driver.implicitly_wait(3)
            return self.page_pre_to_json()

    def get_status(self):
        """Get the selected status data from Fusion."""
        self.driver.get("https://apexfusion.com/api/apex?page=1&per_page=9999")
        self.driver.implicitly_wait(3)
        self.driver.refresh()
        systems = self.page_pre_to_json()

        if not isinstance(systems, list):
            raise RuntimeError("Fusion status response was not a list.")

        for system in systems:
            if str(system.get("_id")) == self.fusion_apex_id:
                return system

        raise RuntimeError(f"Unable to find Fusion status for Apex ID {self.fusion_apex_id}.")

    def prom_metric_string(self, metric_name, metric_labels, metric_value):
        """Format a metric line for Prometheus."""
        metric_name = str(metric_name).lower()
        metric_value = str(metric_value)
        metric_labels = ", ".join(metric_labels)
        return f"apex_{metric_name}{{{metric_labels}}} {metric_value}"

    def mlog_type_eval(self, log_type):
        """Map a numeric Fusion measurement type to a stable label."""
        if log_type == 1:
            return "alkalinity"
        if log_type == 2:
            return "calcium"
        if log_type == 3:
            return "iodine"
        if log_type == 4:
            return "magnesium"
        if log_type == 5:
            return "nitrate"
        if log_type == 6:
            return "phosphate"
        return "other"

    def sensor_type_eval(self, sensor_type):
        """Map a compact sensor type to a stable label."""
        sensor_type = str(sensor_type).lower()
        if sensor_type == "alk":
            return "alkalinity"
        if sensor_type == "ca":
            return "calcium"
        if sensor_type == "mg":
            return "magnesium"
        return sensor_type

    def prometheus_metrics(self):
        """Generate Prometheus metrics for Fusion."""
        metric_lines = []
        fusion_status = self.get_status()
        apex_id = fusion_status["_id"]
        apex_type = fusion_status["type"]
        apex_serial = fusion_status["serial"]
        apex_hardware = fusion_status["hardware"]
        apex_hostname = fusion_status["hostname"]
        apex_software = fusion_status["software"]

        base_label_values = [
            f'apex_id="{apex_id}"',
            f'apex_serial="{apex_serial}"',
            f'apex_hostname="{apex_hostname}"',
        ]

        info_label_values = [
            f'apex_id="{apex_id}"',
            f'apex_type="{apex_type}"',
            f'apex_software="{apex_software}"',
            f'apex_hardware="{apex_hardware}"',
            f'apex_serial="{apex_serial}"',
            f'apex_hostname="{apex_hostname}"',
        ]
        metric_lines.append(self.prom_metric_string("info_label_values", info_label_values, 1))

        sd_card_data = {
            "sd_health": fusion_status["extra"]["sdhealth"],
            "sd_status_read_error": fusion_status["extra"]["sdstat"]["readErr"],
            "sd_status_reads": fusion_status["extra"]["sdstat"]["reads"],
            "sd_status_write_error": fusion_status["extra"]["sdstat"]["writeErr"],
            "sd_status_writes": fusion_status["extra"]["sdstat"]["writes"],
        }
        for metric_name, metric_value in sd_card_data.items():
            metric_lines.append(self.prom_metric_string(metric_name, base_label_values, metric_value))

        for apex_input in fusion_status["status"].get("inputs", []):
            input_label_values = [
                'data_source="apex"',
                f'did="{apex_input["did"]}"',
                f'type="{apex_input["type"]}"',
                f'name="{self.sensor_type_eval(apex_input["name"])}"',
            ]
            combined_labels = base_label_values + input_label_values
            metric_lines.append(
                self.prom_metric_string("measurement", combined_labels, float(apex_input["value"]))
            )

        alarm_labels = [
            f'alarm_description="{str(fusion_status["status"]["alarm"]["smnt"])}"',
            'alarm_values="1 is On, 0 is Off, 2 is metric issue"',
        ]
        combined_labels = base_label_values + alarm_labels
        if fusion_status["status"]["alarm"]["status"] == "OFF":
            alarm_value = 0
        elif fusion_status["status"]["alarm"]["status"] == "ON":
            alarm_value = 1
        else:
            alarm_value = 2
        metric_lines.append(self.prom_metric_string("alarm", combined_labels, alarm_value))

        for apex_module in fusion_status["status"].get("modules", []):
            module_labels = [
                f'module_type="{apex_module["hwtype"]}"',
                f'module_port="{apex_module["abaddr"]}"',
                'module_values="1 is Ok/True, 0 is Not Ok/False, 2 is metric issue"',
            ]
            combined_labels = base_label_values + module_labels
            metric_lines.append(
                self.prom_metric_string(
                    "module_status",
                    combined_labels,
                    1 if apex_module["swstat"] == "OK" else 2,
                )
            )
            metric_lines.append(
                self.prom_metric_string(
                    "module_present",
                    combined_labels,
                    1 if apex_module["present"] is True else 2,
                )
            )

        metric_lines.append(
            self.prom_metric_string(
                "network_quality_pct",
                base_label_values,
                fusion_status["status"]["network"]["quality"],
            )
        )
        metric_lines.append(
            self.prom_metric_string(
                "network_strength_pct",
                base_label_values,
                fusion_status["status"]["network"]["strength"],
            )
        )

        fusion_measurement_log = self.get_measurement_log()
        latest_measurements = {}
        for log_entry in fusion_measurement_log:
            log_date = log_entry["date"]
            log_type = log_entry["type"]
            log_name = log_entry["name"]
            log_value = log_entry["value"]

            try:
                log_timestamp_utc = datetime.datetime.strptime(
                    f"{log_date}+0000", "%Y-%m-%dT%H:%M:%S.%fZ%z"
                )
                current_timestamp_delta_utc = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
                    seconds=self.max_data_age
                )
            except ValueError:
                log_timestamp_utc = datetime.datetime.strptime(str(log_date), "%Y-%m-%dT%H:%M:%S.%fZ")
                current_timestamp_delta_utc = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(
                    seconds=self.max_data_age
                )

            if log_timestamp_utc <= current_timestamp_delta_utc:
                continue

            if log_type in [1, 2, 3, 4, 5, 6]:
                log_name = str(self.mlog_type_eval(log_type)).lower().replace(" ", "_")
            elif log_type in [0]:
                log_name = str(log_name).lower().replace(" ", "_")
            else:
                continue

            if log_name not in latest_measurements:
                latest_measurements[log_name] = {
                    "date": log_date,
                    "type": log_type,
                    "name": log_name,
                    "value": log_value,
                }
            else:
                current_ts_string = datetime.datetime.strptime(
                    latest_measurements[log_name]["date"], "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                incoming_ts_string = datetime.datetime.strptime(log_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                if current_ts_string < incoming_ts_string:
                    latest_measurements[log_name] = {
                        "date": log_date,
                        "type": log_type,
                        "name": log_name,
                        "value": log_value,
                    }

        for latest_measurement_item_dict in latest_measurements.values():
            log_entry_labels = [
                'data_source="measurement_log"',
                f'name="{latest_measurement_item_dict["name"]}"',
            ]
            combined_labels = base_label_values + log_entry_labels
            metric_lines.append(
                self.prom_metric_string(
                    "measurement",
                    combined_labels,
                    float(latest_measurement_item_dict["value"]),
                )
            )

        return "\n".join(metric_lines)


if __name__ == "__main__":
    pass
