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

def setup_logger(name, log_file, level=logging.INFO):
    # Setup logging machanism
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

application_logger = setup_logger('neptune_apex', str(os.path.dirname(__file__)) + '/../logs/' + 'apex.log')
application_logger.info('Application Started')

try:
    loaded_cfg_file = str(os.path.dirname(__file__)) + "/../configuration/" + "apex.yml"
    config_file = open(loaded_cfg_file, 'r')
    configuration = yaml.load(config_file, Loader=yaml.Loader)
except:
    application_logger.error('Configuration File Load Failed')
    exit()

class APEX:
    def __init__(self,apex_ip, auth_module):
        """
        Initializes the APEX class.
        """
        self.epoch_current = math.ceil(time.time())
        self.epoch_past = math.ceil(time.time()) - (60 * 5)
        self.apex_ip = apex_ip
        self.auth_module = auth_module
        self.apex_user = str(configuration["apex_auths"][auth_module]["username"])
        self.apex_password = str(configuration["apex_auths"][auth_module]["password"])
        self.session_cookie = ""

    def authentication(self):
        # Authenticates into Neptune Apex. Returns Session ID.
        url = "http://{}/rest/login".format(self.apex_ip)
        payload = json.dumps({
        "login": self.apex_user,
        "password": self.apex_password,
        "remember_me": False
        })
        headers = {
        'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload, timeout=15)
        response_dict = json.loads(response.text)
    
        if response.status_code == 200:
            self.session_cookie = response_dict['connect.sid']
            return {"authentication" : "successful"}
        else:
            application_logger.error('Apex Authentication Unsuccessful: {}'.format(self.apex_ip))
            return {"authentication" : "unsuccessful"}

    def status(self):
        # Gets status data from the Neptune Apex.
        if self.session_cookie == "":
            self.authentication()
        url = "http://{}/rest/status".format(self.apex_ip)
        payload = {}
        headers = {
        'Content-Type': 'application/json',
        'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        return json.loads(response.text)
    
    def internal_log(self):
        # Gets log data for for sensors onboard the Neptune Apex. Returns Dictionary.
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        url = "http://{}/rest/ilog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
        'Content-Type': 'application/json',
        'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        return json.loads(response.text)
    
    def dos_log(self):
        # Gets log data for the Neptune DOS. Returns Dictionary.
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        url = "http://{}/rest/dlog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
        'Content-Type': 'application/json',
        'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        return json.loads(response.text)
    
    def trident_log(self):
        # Gets data for the Neptune Trident. Returns Dictionary.
        if self.session_cookie == "":
            try:
                self.authentication()
            except Exception as auth_error:
                application_logger.error('Apex Authentication Error: {}'.format(auth_error))
        url = "http://{}/rest/tlog?days=1&sdate=0&_={}".format(self.apex_ip, self.epoch_current)
        payload = {}
        headers = {
        'Content-Type': 'application/json',
        'Cookie': 'connect.sid={}'.format(self.session_cookie)
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        return json.loads(response.text)
    
    def config(self):
        # Gets data for configurable items on the Neptune Apex. Returns Dictionary.
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
        response = requests.request("GET", url, headers=headers, data=payload)
        return json.loads(response.text)

    def prom_metric_string(self, metric_name, metric_labels, metric_value):
        # Formats the metric string properly for Prometheus to read.
        metric_name = str(metric_name).lower()
        metric_value = str(metric_value) # <- Must be Int or Float.
        metric_labels = ', '.join(metric_labels)
        return "apex_{}{{{}}} {}".format(metric_name, metric_labels, metric_value)
    
    def prometheus_metrics(self):
        metric_lines = []
        apex_status = self.status()

        hostname = apex_status["system"]["hostname"] #Ex: "Reefer_250"
        serial = apex_status["system"]["serial"] #EX: "AC6J:13147"
        type = apex_status["system"]["type"] #EX: "AC6J"
        software = apex_status["system"]["software"] #Ex: "5.12J_7D24"
        hardware = apex_status["system"]["hardware"] #EX: "1.0"

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
            input_label_values =[
            'input_did="{}"'.format(apex_input["did"]), #Ex: "3_2" -
            'input_type="{}"'.format(apex_input["type"]), #Ex: "mg" -
            'input_name="{}"'.format(apex_input["name"]) #Ex: "Mg" -
            #'input_value="{}"'.format(apex_input["value"]), #Ex: 1586
            ]
            combined_labels = base_label_values + input_label_values
            apex_input_value = apex_input["value"]
            metric_lines.append(self.prom_metric_string(label_name, combined_labels, apex_input_value))
        
        return "\n".join(metric_lines)

if __name__ == "__main__":
    pass