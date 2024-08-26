"""
Neptune Apex API Module.
"""
import json
import time
import math
import os
import logging.config
import requests
import yaml
import logging
import os

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

log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'apex.log')
application_logger = setup_logger('neptune_apex', log_file)

try:
    loaded_cfg_file = os.path.join(os.path.dirname(__file__), '..', 'configuration', 'apex.yml')
    with open(loaded_cfg_file, 'r') as config_file:
        configuration = yaml.load(config_file, Loader=yaml.Loader)
except Exception as e:
    application_logger.error('Configuration File Load Failed: {}'.format(e))
    exit()

class APEX:
    def __init__(self, apex_ip, auth_module, apex_debug=False):
        """
        Initializes the APEX class.
        Parameters:
            - apex_ip (str): The IP address of the APEX device.
            - auth_module (str): The authentication module to use for APEX.

            Attributes:
            - epoch_current (int): The current epoch time.
            - date_string (str): The current date.
            - epoch_past (int): The epoch time 5 minutes ago.
            - apex_ip (str): The IP address of the APEX device.
            - auth_module (str): The authentication module to use for APEX.
            - apex_user (str): The username for APEX authentication.
            - apex_password (str): The password for APEX authentication.
            - session_cookie (str): The session cookie for APEX authentication.
        """
        # Going forward if a date range is need as a url pram. implement an apex_debug check.
        # Include at least 1-7 days of data.
        self.epoch_current = math.ceil(time.time())
        self.date_string = time.strftime("%Y-%m-%d")
        self.epoch_past = math.ceil(time.time()) - (60 * 5)
        self.apex_ip = apex_ip
        self.auth_module = auth_module
        self.apex_user = str(configuration["apex_auths"][auth_module]["username"])
        self.apex_password = str(configuration["apex_auths"][auth_module]["password"])
        self.session_cookie = ""
        self.apex_debug = apex_debug


    def authentication(self):
        """
        Authenticates into Neptune Apex. Returns Session ID.

        Returns:
            dict: A dictionary containing the authentication result. The dictionary has the following keys:
                - "authentication": The authentication result, which can be "successful", "unsuccessful", or "error".
        """
        url = "http://{}/rest/login".format(self.apex_ip)
        payload = json.dumps({
            "login": self.apex_user,
            "password": self.apex_password,
            "remember_me": False
        })
        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                self.session_cookie = response_dict['connect.sid']
                return {"authentication": "successful"}
            else:
                application_logger.error('Apex Authentication Unsuccessful: {}'.format(self.apex_ip))
                application_logger.error('url_response: {}'.format(response))
                return {"authentication": "unsuccessful"}
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex Authentication Error: {}'.format(e))
            return {"authentication": "error"}

    def status(self):
        """
        Gets status data from the Neptune Apex.

        Returns:
            dict or None: The status data as a dictionary if the request is successful, 
            otherwise None.

        Raises:
            requests.exceptions.RequestException: If there is an error in making the request.
        """
        if self.session_cookie == "":
            self.authentication()
        url = "http://{}/rest/status".format(self.apex_ip)
        payload = {}
        headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                return response_dict
            else:
                application_logger.error('Apex Status Error: {}'.format(response_dict))
                return None
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex Status Error: {}'.format(e))
            return None
    
    def internal_log(self):
        """
        Gets log data for sensors onboard the Neptune Apex.

        Returns:
            dict: A dictionary containing the log data.

        Raises:
            Exception: If there is an authentication error.
            requests.exceptions.RequestException: If there is an error making the request.
        """
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        if self.apex_debug == True:
            url = "http://{}/rest/ilog?days=365".format(self.apex_ip)
        else:
            url = "http://{}/rest/ilog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                return response_dict
            else:
                application_logger.error('Apex Internal Log Error: {}'.format(response_dict))
                return None
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex Internal Log Error: {}'.format(e))
            return None
    
    def dos_log(self):
        """
        Gets log data for the Neptune DOS.

        Returns:
            dict: Dictionary containing the log data for the Neptune DOS.

        Raises:
            Exception: If there is an authentication error during the process.
            requests.exceptions.RequestException: If there is an error while making the HTTP request.
        """
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        if self.apex_debug == True:
            url = "http://{}/rest/dlog?sdate={}&".format(self.apex_ip, self.date_string)
        else:
            url = "http://{}/rest/dlog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                return response_dict
            else:
                application_logger.error('Apex DOS Log Error: {}'.format(response_dict))
                return None
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex DOS Log Error: {}'.format(e))
            return None
    
    def trident_log(self):
        """
        Gets data for the Neptune Trident.

        Returns:
            dict: A dictionary containing the response data from the Neptune Trident.
                  If the response status code is 200, the dictionary will contain the response data.
                  Otherwise, it will return None.

        Raises:
            Exception: If there is an authentication error during the process.
            requests.exceptions.RequestException: If there is an error during the HTTP request.

        """
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        if self.apex_debug == True:
            url = "http://{}/rest/tlog?days=7&sdate={}".format(self.apex_ip, self.date_string)
        else:
            url = "http://{}/rest/tlog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                return response_dict
            else:
                application_logger.error('Apex Trident Log Error: {}'.format(response_dict))
                return None
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex Trident Log Error: {}'.format(e))
            return None
    
    def config(self):
        """
        Gets data for configurable items on the Neptune Apex.

        Returns:
            dict: A dictionary containing the response data from the Neptune Apex.

        Raises:
            Exception: If there is an authentication error during the process.
            requests.exceptions.RequestException: If there is an error during the request.

        """
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        url = "http://{}/rest/config".format(self.apex_ip)
        payload = {}
        headers = {
            'Content-Type': 'application/json',
            'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=15)
            response_dict = response.json()
            if response.status_code == 200:
                return response_dict
            else:
                application_logger.error('Apex Config Error: {}'.format(response_dict))
                return None
        except requests.exceptions.RequestException as e:
            application_logger.error('Apex Config Error: {}'.format(e))
            return None

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
        metric_value = str(metric_value)  # Must be Int or Float.
        metric_labels = ', '.join(metric_labels)
        return "apex_{}{{{}}} {}".format(metric_name, metric_labels, metric_value)
    
    def prometheus_metrics(self):
        """
        Generates Prometheus metrics for the Neptune Apex device.

        Returns:
            str: The metrics data in Prometheus format.
        """
        metric_lines = []
        apex_status = self.status()

        hostname = apex_status["system"]["hostname"]
        serial = apex_status["system"]["serial"]
        type = apex_status["system"]["type"]
        software = apex_status["system"]["software"]
        hardware = apex_status["system"]["hardware"]

        base_label_values = [
            'apex_serial="{}"'.format(serial),
            'apex_hostname="{}"'.format(hostname)
        ]

        # INFO METRIC
        info_labels = [
            'apex_type="{}"'.format(type),
            'apex_software="{}"'.format(software),
            'apex_hardware="{}"'.format(hardware),
            'apex_serial="{}"'.format(serial),
            'apex_hostname="{}"'.format(hostname)
        ]
        metric_lines.append(self.prom_metric_string("apex_info_label_values", info_labels, 0))

        # SENSOR METRICS
        apex_inputs = apex_status["inputs"]
        for apex_input in apex_inputs:
            label_name = "sensor_{}".format(str(apex_input["name"]).lower())
            input_label_values = [
                'input_did="{}"'.format(apex_input["did"]),
                'input_type="{}"'.format(apex_input["type"]),
                'input_name="{}"'.format(apex_input["name"])
            ]
            combined_labels = base_label_values + input_label_values
            apex_input_value = apex_input["value"]
            metric_lines.append(self.prom_metric_string(label_name, combined_labels, apex_input_value))

        return "\n".join(metric_lines)

if __name__ == "__main__":
    pass