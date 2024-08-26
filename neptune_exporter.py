"""
Neptune Apex Exporter for Prometheus.
"""
import json
import time
import math
import socket
import os
import requests
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Response, status, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
import yaml
from neptune_modules import neptune_apex
from neptune_modules import neptune_fusion
import logging.config

def setup_logger(name, log_file, level=logging.INFO):
    """
    Set up the logger for the application.

    Args:
        name (str): The name of the logger.
        log_file (str): The path to the log file.
        level (int): The logging level.

    Returns:
        logger (logging.Logger): The configured logger.
    """
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

application_logger = setup_logger('neptune_exporter', str(os.path.dirname(__file__)) + '/logs/' + 'exporter.log')

try:
    loaded_cfg_file = str(os.path.dirname(__file__)) + "/configuration/" + "exporter.yml"
    config_file = open(loaded_cfg_file, 'r')
    configuration = yaml.load(config_file, Loader=yaml.Loader)
except:
    application_logger.error('Configuration File Load Failed')
    exit()

app = FastAPI(
    title="Apex Exporter",
    summary="Prometheus Exporter for the Neptune Apex.",
    description="https://github.com/dl-romero/apex_exporter",
    version="1.0",
    contact={
        "name": "dromero.dev",
        "url": "https://dromero.dev"
    },
    license_info={
        "name": "License",
        "url": "https://github.com/dl-romero/apex_exporter/blob/main/LICENSE",
    },
    openapi_tags=[
        {
            "name": "Apex",
            "description": "Get Apex Metrics in Prometheus Format",
        },
        {
            "name": "Fusion",
            "description": "Get Fusion Metrics in Prometheus Format",
        },
        {
            "name": "Logs",
            "description": "View Apex Exporter Logs",
        }
    ]
)

@app.get("/metrics/apex", response_class=PlainTextResponse, tags=["Apex"])
async def apex_prometheus_metrics(target, auth_module):
    """
    Get Apex metrics in Prometheus format.

    Args:
        target (str): The IP address of the Apex device.
        auth_module (str): The authentication module.

    Returns:
        str: The Prometheus metrics.
    """
    apex_direct = neptune_apex.APEX(apex_ip=target, auth_module=auth_module)
    return apex_direct.prometheus_metrics()

@app.get("/metrics/fusion", response_class=PlainTextResponse, tags=["Fusion"])
async def fusion_prometheus_metrics(data_max_age, fusion_apex_id):
    """
    Get Fusion metrics in Prometheus format.

    Args:
        data_max_age (int): The maximum age of the data.
        fusion_apex_id (str): The ID of the Fusion Apex.

    Returns:
        str: The Prometheus metrics.
    """
    apex_fusion = neptune_fusion.FUSION(fusion_apex_id, data_max_age)
    return apex_fusion.prometheus_metrics()

@app.get("/logs/", response_class=PlainTextResponse, tags=["Logs"])
async def apex_exporter_logs(log_file_name):
    """
    View Apex Exporter logs.

    Args:
        log_file_name (str): The name of the log file.

    Returns:
        str: The contents of the log file.
    """
    if log_file_name in ['neptune.log', 'exporter.log', 'apex.log']:
        log_file = str(os.path.dirname(__file__)) + '/logs/' + 'neptune_exporter.log'
        with open(log_file, "r") as open_file:
            return "".join(open_file.readlines())
    else:
        return "Log name not found. Use one of ('neptune.log', 'exporter.log', 'apex.log') without any quotes."

@app.get("/", include_in_schema=False)
async def documentation_home_page():
    """
    Redirect to the documentation home page.

    Returns:
        RedirectResponse: The redirect response.
    """
    return RedirectResponse(url='/docs')

if __name__ == "__main__":
    server_hostname = socket.gethostname()
    app_name = Path(__file__).stem
    uvicorn.run("{}:app".format(app_name), host=server_hostname, port=5006, log_level="info")
