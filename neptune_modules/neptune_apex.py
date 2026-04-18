"""Neptune Apex API module."""

import logging
import math
import time
from pathlib import Path

import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "configuration" / "apex.yml"
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


application_logger = setup_logger("neptune_apex", LOG_DIR / "apex.log")


def load_configuration() -> dict:
    """Load the Apex configuration from disk safely."""
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            loaded_config = yaml.safe_load(config_file) or {}
    except FileNotFoundError as exc:
        raise RuntimeError(f"Apex configuration file not found: {CONFIG_PATH}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in Apex configuration: {CONFIG_PATH}") from exc

    if not isinstance(loaded_config, dict):
        raise RuntimeError("Apex configuration must be a dictionary.")

    return loaded_config


try:
    configuration = load_configuration()
except RuntimeError as exc:
    application_logger.exception("Configuration File Load Failed: %s", exc)
    raise SystemExit(1) from exc


class APEX:
    """Client for the local Neptune Apex REST API."""

    REQUEST_TIMEOUT = 15

    def __init__(self, apex_ip, auth_module, apex_debug=False):
        self.epoch_current = math.ceil(time.time())
        self.date_string = time.strftime("%Y-%m-%d")
        self.epoch_past = math.ceil(time.time()) - (60 * 5)
        self.apex_ip = str(apex_ip)
        self.auth_module = auth_module
        self.apex_debug = apex_debug
        self.session_cookie = ""

        auth_config = configuration.get("apex_auths", {}).get(auth_module)
        if not auth_config:
            raise ValueError(f"Unknown Apex auth module: {auth_module}")

        self.apex_user = str(auth_config["username"])
        self.apex_password = str(auth_config["password"])

    def _request_json(self, url, method="get", payload=None):
        """Make a JSON request to the Apex controller."""
        headers = {"Content-Type": "application/json"}
        if self.session_cookie:
            headers["Cookie"] = f"connect.sid={self.session_cookie}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            application_logger.error("Apex request failed for %s: %s", url, exc)
            return None
        except ValueError as exc:
            application_logger.error("Apex response was not valid JSON for %s: %s", url, exc)
            return None

    def authentication(self):
        """Authenticate to Neptune Apex and return the session status."""
        url = f"http://{self.apex_ip}/rest/login"
        payload = {
            "login": self.apex_user,
            "password": self.apex_password,
            "remember_me": False,
        }
        response_dict = self._request_json(url, method="post", payload=payload)
        if response_dict and response_dict.get("connect.sid"):
            self.session_cookie = response_dict["connect.sid"]
            return {"authentication": "successful"}

        application_logger.error("Apex authentication unsuccessful: %s", self.apex_ip)
        return {"authentication": "error"}

    def status(self):
        """Get status data from the Neptune Apex."""
        if not self.session_cookie:
            self.authentication()
        return self._request_json(f"http://{self.apex_ip}/rest/status")

    def internal_log(self):
        """Get onboard sensor log data from the Neptune Apex."""
        if not self.session_cookie:
            self.authentication()
        if self.apex_debug:
            url = f"http://{self.apex_ip}/rest/ilog?days=365"
        else:
            url = f"http://{self.apex_ip}/rest/ilog?days=1&sdate=0&_={self.epoch_current}"
        return self._request_json(url)

    def dos_log(self):
        """Get Neptune DOS log data."""
        if not self.session_cookie:
            self.authentication()
        if self.apex_debug:
            url = f"http://{self.apex_ip}/rest/dlog?sdate={self.date_string}&"
        else:
            url = f"http://{self.apex_ip}/rest/dlog?days=1&sdate=0&_={self.epoch_current}"
        return self._request_json(url)

    def trident_log(self):
        """Get Neptune Trident log data."""
        if not self.session_cookie:
            self.authentication()
        if self.apex_debug:
            url = f"http://{self.apex_ip}/rest/tlog?days=7&sdate={self.date_string}"
        else:
            url = f"http://{self.apex_ip}/rest/tlog?days=1&sdate=0&_={self.epoch_current}"
        return self._request_json(url)

    def config(self):
        """Get configurable item data from the Neptune Apex."""
        if not self.session_cookie:
            self.authentication()
        return self._request_json(f"http://{self.apex_ip}/rest/config")

    def normalize_metric_value(self, metric_value):
        """Normalize metric values into Prometheus-safe numbers."""
        if isinstance(metric_value, bool):
            return 1 if metric_value else 0

        if isinstance(metric_value, (int, float)):
            return metric_value

        string_value = str(metric_value).strip().lower()
        mapped_values = {
            "on": 1,
            "off": 0,
            "open": 1,
            "closed": 0,
            "ok": 1,
            "error": 0,
        }
        if string_value in mapped_values:
            return mapped_values[string_value]

        try:
            return float(string_value)
        except ValueError as exc:
            raise ValueError(f"Unsupported metric value: {metric_value}") from exc

    def prom_metric_string(self, metric_name, metric_labels, metric_value):
        """Format a metric line for Prometheus."""
        metric_name = str(metric_name).lower()
        metric_value = self.normalize_metric_value(metric_value)
        metric_labels = ", ".join(metric_labels)
        return f"apex_{metric_name}{{{metric_labels}}} {metric_value}"

    def prometheus_metrics(self):
        """Generate Prometheus metrics for the Neptune Apex device."""
        metric_lines = []
        apex_status = self.status()
        if not apex_status or "system" not in apex_status:
            raise RuntimeError("Unable to retrieve Apex status data.")

        hostname = apex_status["system"]["hostname"]
        serial = apex_status["system"]["serial"]
        apex_type = apex_status["system"]["type"]
        software = apex_status["system"]["software"]
        hardware = apex_status["system"]["hardware"]

        base_label_values = [
            f'apex_serial="{serial}"',
            f'apex_hostname="{hostname}"',
        ]

        info_labels = [
            f'apex_type="{apex_type}"',
            f'apex_software="{software}"',
            f'apex_hardware="{hardware}"',
            f'apex_serial="{serial}"',
            f'apex_hostname="{hostname}"',
        ]
        metric_lines.append(self.prom_metric_string("apex_info_label_values", info_labels, 1))

        for apex_input in apex_status.get("inputs", []):
            label_name = f"sensor_{str(apex_input['name']).lower()}"
            input_label_values = [
                f'input_did="{apex_input["did"]}"',
                f'input_type="{apex_input["type"]}"',
                f'input_name="{apex_input["name"]}"',
            ]
            combined_labels = base_label_values + input_label_values
            apex_input_value = apex_input.get("value")
            try:
                metric_lines.append(self.prom_metric_string(label_name, combined_labels, apex_input_value))
            except ValueError:
                application_logger.warning(
                    "Skipping unsupported Apex metric value for %s: %s",
                    label_name,
                    apex_input_value,
                )

        return "\n".join(metric_lines)


if __name__ == "__main__":
    pass
