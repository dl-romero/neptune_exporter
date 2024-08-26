"""
Neptune Fusion Web-Scrape API Module.
"""
import datetime
import json
import logging.config
import os
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.options import Options

def setup_logger(name, log_file, level=logging.INFO):
    """
    Set up a logger with the specified name, log file, and log level.

    Args:
        name (str): The name of the logger.
        log_file (str): The path to the log file.
        level (int, optional): The log level. Defaults to logging.INFO.

    Returns:
        logging.Logger: The configured logger.
    """
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

application_logger = setup_logger('neptune_fusion', str(os.path.dirname(__file__)) + '/../logs/' + 'neptune.log')

try:
    loaded_cfg_file = str(os.path.dirname(__file__)) + "/../configuration/" + "fusion.yml"
    with open(loaded_cfg_file, 'r') as config_file:
        configuration = yaml.load(config_file, Loader=yaml.Loader)
except Exception as e:
    application_logger.error('Configuration File Load Failed: {}'.format(str(e)))
    exit()

class FUSION:
    """
    This class uses webscraping to authenticate into FUSION and query APIs that are dynamically built using JS. Unlike a direct APEX (local) API.
    """
    def __init__(self, fusion_apex_id, max_data_age, fusion_debug=False):
        """
        Initializes the web-scraper and gets stored credentials.

        Args:
            fusion_apex_id (str): The ID of the Fusion Apex system.
            max_data_age (int): The maximum age of data to retrieve.

        """
        # Going forward if a date range is need as a url pram. implement an fusion_debug check.
        # Include at least 1-7 days of data.
        self.fusion_debug = fusion_debug
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.fusion_login(configuration["fusion"]["apex_systems"][fusion_apex_id]["username"], 
                          configuration["fusion"]["apex_systems"][fusion_apex_id]["password"])
        self.fusion_apex_id = fusion_apex_id
        self.max_data_age = int(max_data_age) + 60 # 1m grace period to account for scrape time.

    def fusion_login(self, username, password):
        """
        Logs into Fusion.

        Args:
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self.driver.get('https://apexfusion.com/login')
        id_box = WebDriverWait(self.driver, 30).until(expected_conditions.presence_of_element_located((By.ID, 'index-login-username')))
        id_box.send_keys(str(username))
        pass_box = self.driver.find_element(By.ID, 'index-login-password')
        pass_box.send_keys(str(password))
        self.driver.find_element(By.CLASS_NAME, 'af-sign-in').click()
        self.driver.implicitly_wait(3)

    def get_measurement_log(self):
        """
        Gets the measurement log from Fusion.

        Returns:
            dict: The measurement log data in JSON format.
        """
        if self.fusion_debug == True:
            mlog_url = "https://apexfusion.com/api/apex/{}/mlog?days=365".format(str(self.fusion_apex_id))
        else:
            mlog_url = "https://apexfusion.com/api/apex/{}/mlog?days=1".format(str(self.fusion_apex_id))
        self.driver.get(mlog_url)
        self.driver.implicitly_wait(3)
        self.driver.refresh()
        html_content = str(self.driver.page_source)
        html_content = html_content[html_content.index("<pre>") + len("<pre>"):]
        html_content = html_content[:html_content.index("</pre>") + len("</pre>")]
        html_content = html_content.replace("<pre>", "")
        html_content = html_content.replace("</pre>", "")
        html_to_json = json.loads(html_content)
        return html_to_json
    
    def get_status(self):
        """
        Gets the status data from Fusion.

        Returns:
            dict: The status data in JSON format.
        """
        mlog_url = "https://apexfusion.com/api/apex?page=1&per_page=9999"
        self.driver.get(mlog_url)
        self.driver.implicitly_wait(3)
        self.driver.refresh()
        html_content = str(self.driver.page_source)
        html_content = html_content[html_content.index("<pre>") + len("<pre>"):]
        html_content = html_content[:html_content.index("</pre>") + len("</pre>")]
        html_content = html_content.replace("<pre>", "")
        html_content = html_content.replace("</pre>", "")
        html_to_json = json.loads(html_content)
        return html_to_json
    
    def prom_metric_string(self, metric_name, metric_labels, metric_value):
        """
        Formats the metric string properly for Prometheus to read.

        Args:
            metric_name (str): The name of the metric.
            metric_labels (list): The labels associated with the metric.
            metric_value (int or float): The value of the metric.

        Returns:
            str: The formatted metric string for Prometheus.
        """
        metric_name = str(metric_name).lower()
        metric_value = str(metric_value) # <- Must be Int or Float.
        metric_labels = ', '.join(metric_labels)
        return "apex_{}{{{}}} {}".format(metric_name, metric_labels, metric_value)

    def mlog_type_eval(self, log_type):
        """
        Evaluates the log type and returns a more proper name.

        Args:
            log_type (int): The type of the log.

        Returns:
            str: The proper name for the log type.
        """
        if log_type == 1:
            return "alkalinity"
        elif log_type == 2:
            return "calcium"
        elif log_type == 3:
            return "iodine"
        elif log_type == 4:
            return "magnesium"
        elif log_type == 5:
            return "nitrate"
        elif log_type == 6:
            return "phosphate"
        else:
            return "other"
        
    def sensor_type_eval(self, sensor_type):
        """
        Evaluates the sensor type and returns a more proper name.

        Args:
            sensor_type (str): The type of the sensor.

        Returns:
            str: The proper name for the sensor type.
        """
        sensor_type = str(sensor_type).lower()
        if sensor_type == "alk":
            return "alkalinity"
        elif sensor_type == "ca":
            return "calcium"
        elif sensor_type == "mg":
            return "magnesium"
        else:
            return str(sensor_type).lower()
    
    def prometheus_metrics(self):
        """
        Generates Prometheus metrics for Fusion.

        Returns:
            str: The metrics data in Prometheus format.
        """
        metric_lines = []
        fusion_status = self.get_status()[0]
        apex_id = fusion_status["_id"]
        apex_type = fusion_status["type"]
        apex_serial = fusion_status["serial"]
        apex_hardware = fusion_status["hardware"]
        apex_hostname = fusion_status["hostname"]
        apex_software = fusion_status["software"]

        base_label_values = [
            'apex_id="{}"'.format(apex_id),
            'apex_serial="{}"'.format(apex_serial),
            'apex_hostname="{}"'.format(apex_hostname)
        ]

        # INFO METRIC
        info_label_values = [
            'apex_id="{}"'.format(apex_id),
            'apex_type="{}"'.format(apex_type),
            'apex_software="{}"'.format(apex_software),
            'apex_hardware="{}"'.format(apex_hardware),
            'apex_serial="{}"'.format(apex_serial),
            'apex_hostname="{}"'.format(apex_hostname)
        ]
        metric_lines.append(self.prom_metric_string("info_label_values", info_label_values, 0))

        # SD CARD METRICS
        sd_card_data = {
            "sd_health": fusion_status["extra"]["sdhealth"],
            "sd_status_read_error": fusion_status["extra"]["sdstat"]["readErr"],
            "sd_status_reads": fusion_status["extra"]["sdstat"]["reads"],
            "sd_status_write_error": fusion_status["extra"]["sdstat"]["writeErr"],
            "sd_status_writes": fusion_status["extra"]["sdstat"]["writes"]
        }
        for metric_name, metric_value in sd_card_data.items():
            metric_lines.append(self.prom_metric_string(metric_name, base_label_values, metric_value))

        # SENSOR METRICS
        apex_inputs = fusion_status["status"]["inputs"]
        for apex_input in apex_inputs:
            input_label_values = [
                'data_source="apex"',
                'did="{}"'.format(apex_input["did"]),  # Ex: "3_2"
                'type="{}"'.format(apex_input["type"]),  # Ex: "mg"
                'name="{}"'.format(self.sensor_type_eval(apex_input["name"]))  # Ex: "Mg"
                # 'value="{}"'.format(apex_input["value"]), #Ex: 1586
            ]
            combined_labels = base_label_values + input_label_values
            apex_input_value = apex_input["value"]
            metric_lines.append(self.prom_metric_string("measurement", combined_labels, float(apex_input_value)))

        # ALARM METRICS
        alarm_labels = ['alarm_description="{}"'.format(str(fusion_status["status"]["alarm"]["smnt"])),
                        'alarm_values="1 is On, 0 is Off, 2 is metric issue"'
                        ]
        combined_labels = base_label_values + alarm_labels
        if fusion_status["status"]["alarm"]["status"] == "OFF":
            alarm_value = 0
        elif fusion_status["status"]["alarm"]["status"] == "ON":
            alarm_value = 1
        else:
            alarm_value = 2
        metric_lines.append(self.prom_metric_string("alarm", combined_labels, alarm_value))

        # MODULE METRICS
        apex_modules = fusion_status["status"]["modules"]
        for apex_module in apex_modules:
            apex_module_ab_address = apex_module["abaddr"]  # EX: 2
            apex_module_type = apex_module["hwtype"]  # "DQD"
            apex_module_status = apex_module["swstat"]  # "OK"
            apex_module_present = apex_module["present"]  # true
            module_labels = ['module_type="{}"'.format(apex_module_type),
                             'module_port="{}"'.format(apex_module_ab_address),
                             'module_values="1 is Ok/True, 0 is Not Ok/False, 2 is metric issue"'
                             ]
            combined_labels = base_label_values + module_labels
            if apex_module_status == "OK":
                apex_module_status_value = 1
            else:
                apex_module_status_value = 2
            metric_lines.append(self.prom_metric_string("module_status", combined_labels, apex_module_status_value))

            if apex_module_present == True:
                apex_module_present_value = 1
            else:
                apex_module_present_value = 2
            metric_lines.append(self.prom_metric_string("module_present", combined_labels, apex_module_present_value))

        # APEX NETWORK
        apex_network_quality = fusion_status["status"]["network"]["quality"]
        metric_lines.append(self.prom_metric_string("network_quality_pct", base_label_values, apex_network_quality))
        apex_network_strength = fusion_status["status"]["network"]["strength"]
        metric_lines.append(self.prom_metric_string("network_strength_pct", base_label_values, apex_network_strength))

        # GET LATEST MEASUREMENTS
        fusion_measurement_log = self.get_measurement_log()
        latest_measurements = {}
        for log_entry in fusion_measurement_log:
            log_date = log_entry["date"]  # Ex: 2024-08-19T04:20:38.184Z
            log_type = log_entry["type"]
            log_name = log_entry["name"]
            log_value = log_entry["value"]

            try:
                log_timestamp_utc = datetime.datetime.strptime(str(log_date) + "+0000", "%Y-%m-%dT%H:%M:%S.%fZ%z")
                current_timestamp_delta_utc = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
                    seconds=self.max_data_age)
                if log_timestamp_utc <= current_timestamp_delta_utc:
                    continue
            except:
                log_timestamp_utc = datetime.datetime.strptime(str(log_date), "%Y-%m-%dT%H:%M:%S.%fZ")
                current_timestamp_delta_utc = datetime.datetime.utcnow() - datetime.timedelta(
                    seconds=self.max_data_age)
                if log_timestamp_utc <= current_timestamp_delta_utc:
                    continue

            if log_type in [1, 2, 3, 4, 5, 6]:
                log_name = str(str(self.mlog_type_eval(log_type)).lower()).replace(" ", "_")
                if str(log_name) not in latest_measurements:
                    latest_measurements[str(log_name)] = {
                        "date": log_date,
                        "type": log_type,
                        "name": log_name,
                        "value": log_value
                    }
                else:
                    current_ts_string = datetime.datetime.strptime(latest_measurements[str(log_name)]["date"],
                                                                   "%Y-%m-%dT%H:%M:%S.%fZ")
                    incoming_ts_string = datetime.datetime.strptime(log_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if current_ts_string < incoming_ts_string:
                        latest_measurements[str(log_name)] = {
                            "date": log_date,
                            "type": log_type,
                            "name": log_name,
                            "value": log_value
                        }

            if log_type in [0]:
                log_name = str(str(log_name)).lower().replace(" ", "_")
                if str(log_name) not in latest_measurements:
                    latest_measurements[str(log_name)] = {
                        "date": log_date,
                        "type": log_type,
                        "name": log_name,
                        "value": log_value
                    }
                else:
                    current_ts_string = datetime.datetime.strptime(latest_measurements[str(log_name)]["date"],
                                                                   "%Y-%m-%dT%H:%M:%S.%fZ")
                    incoming_ts_string = datetime.datetime.strptime(log_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    if current_ts_string < incoming_ts_string:
                        latest_measurements[str(log_name)] = {
                            "date": log_date,
                            "type": log_type,
                            "name": log_name,
                            "value": log_value
                        }
        for latest_measurement_item, latest_measurement_item_dict in latest_measurements.items():
            log_entry_labels = [
                'data_source="measurement_log"',
                'name="{}"'.format(latest_measurement_item_dict["name"])
            ]
            combined_labels = base_label_values + log_entry_labels
            latest_measurement_item_value = latest_measurement_item_dict["value"]
            metric_lines.append(self.prom_metric_string("measurement", combined_labels, float(latest_measurement_item_value)))
        # RETURN DATA
        return "\n".join(metric_lines)

if __name__ == "__main__":
    pass

