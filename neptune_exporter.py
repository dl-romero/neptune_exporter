"""
Neptune Apex Exporter for Prometheus.
"""
import json
import socket
import os
import glob
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Response, status, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.responses import FileResponse
import yaml
from neptune_modules import neptune_apex
from neptune_modules import neptune_fusion
import logging.config
import shutil
import datetime

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
    title="Neptune Exporter",
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
            "name": "Export Logs",
            "description": "Download Neptune Exporter Log data.",
        },
        {
            "name": "Export Apex JSON Files",
            "description": "Download Apex JSON data.",
        },
        {
            "name": "Export Fusion JSON Files",
            "description": "Download Fusion JSON data.",
        }
    ]
)

def clean_workspace():
    """
    Cleans the workspace directory by removing all files and directories within it.
    Returns:
        bool: True if the workspace is successfully cleaned, False if the workspace is locked.
    """

    # Defining Work Space
    workspace_directory = os.path.join(os.path.dirname(__file__), "workspace")

    # Check Workspace Lock / Lock Workspace
    if os.path.isfile(workspace_directory + "WORKSPACE_LOCKED") == True:
        return False

    # Cleaning Work Space
    files = glob.glob('{}/*'.format(workspace_directory))
    for f in files:
        if os.path.isfile(f):
            os.remove(f)
        if os.path.isdir(f):
            try:
                os.rmdir(f)
            except:
                shutil.rmtree(f)
    return True

def is_file_older_than(file, delta): 
    """
    Checks if a file is older than a specified time delta.
    Args:
        file (str): The path to the file.
        delta (datetime.timedelta): The time delta to compare against.
    Returns:
        bool: True if the file is older than the specified time delta, False otherwise.
    """

    cutoff = datetime.datetime.utcnow() - delta
    mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(file))
    if mtime < cutoff:
        return True
    return False

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

@app.get("/export/logs/", response_class=PlainTextResponse, tags=["Export Log Data"])
async def apex_exporter_logs():
    """
    Export and download logs.

    This function creates a zip archive of the logs directory and returns it as a FileResponse object.

    Returns:
        FileResponse: The zip archive containing the logs.
    """
    log_directory = os.path.join(os.path.dirname(__file__), 'logs')
    workspace_directory = os.path.join(os.path.dirname(__file__), 'workspace')
    
    # Check Workspace Lock / Lock Workspace
    if is_file_older_than(workspace_directory + "/WORKSPACE_LOCKED", datetime.timedelta(seconds=300)) == False or os.path.isfile(workspace_directory + "WORKSPACE_LOCKED") == True:
        return "Export Workspace Locked. Please run 1 export at a time.\nIf an error occurred and the lock is still in place. Wait 5 minutes and try again."
    
    # Cleaning Work Space
    clean_workspace()

    # Locking Workspace
    with open(os.path.join(workspace_directory, "WORKSPACE_LOCKED"), "w") as lock_file:
        lock_file.close()

    # Compress files in workspace/temp_files. Zip is located in workspace
    file_name_ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"neptune_exporter-logs.{file_name_ts}"
    shutil.make_archive(os.path.join(workspace_directory, file_name), format='zip', root_dir=log_directory)

    # Remove Workspace Lock and Provide Download
    os.remove(workspace_directory + "/WORKSPACE_LOCKED")
    return FileResponse(os.path.join(workspace_directory, f"{file_name}.zip"), media_type='application/octet-stream', filename=f"{file_name}.zip")

@app.get("/export/apex/", response_class=PlainTextResponse, tags=["Export Apex JSON Files"])
async def export_apex_json(target, auth_module):
    """
    Export Apex JSON data from Neptune Apex device.
    Args:
        target (str): The IP address of the Neptune Apex device.
        auth_module (str): The authentication module to be used.
    Returns:
        FileResponse: The response containing the exported JSON data in a zip file.
    Raises:
        FileNotFoundError: If the workspace directory or any required files are not found.
        Exception: If the workspace is locked or an error occurs during the export process.
    """

    # Defining Work Space
    workspace_directory = os.path.join(os.path.dirname(__file__), "workspace")

    # Check Workspace Lock / Lock Workspace
    if is_file_older_than(workspace_directory + "/WORKSPACE_LOCKED", datetime.timedelta(seconds=300)) == False or os.path.isfile(workspace_directory + "WORKSPACE_LOCKED") == True:
        return "Export Workspace Locked. Please run 1 export at a time.\nIf an error occurred and the lock is still in place. Wait 5 minutes and try again."

    # Cleaning Work Space
    clean_workspace()

    # Locking Workspace
    with open(os.path.join(workspace_directory, "WORKSPACE_LOCKED"), "w") as lock_file:
        lock_file.close()

    # Creating JSON Folder
    temp_files_folder = os.path.join(workspace_directory, "temp_files")
    if os.path.isdir(temp_files_folder) == False:
        os.mkdir(temp_files_folder)

    # Setting up Neptune Apex Class in Debug Mode
    apex_direct = neptune_apex.APEX(apex_ip=target, auth_module=auth_module, apex_debug = True)
    
    # Status JSON
    with open(os.path.join(temp_files_folder, "status.json"), "w") as data_file:
        json.dump(apex_direct.status(), data_file, indent=4, sort_keys=True)
        data_file.close()
    
    # ILOG JSON
    with open(os.path.join(temp_files_folder, "ilog.json"), "w") as data_file:
        json.dump(apex_direct.internal_log(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # DOS JSON
    with open(os.path.join(temp_files_folder, "dlog.json"), "w") as data_file:
        json.dump(apex_direct.dos_log(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # Trident JSON
    with open(os.path.join(temp_files_folder, "tlog.json"), "w") as data_file:
        json.dump(apex_direct.trident_log(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # Config JSON
    with open(os.path.join(temp_files_folder, "config.json"), "w") as data_file:
        json.dump(apex_direct.trident_log(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # Compress files in workspace/temp_files. Zip is located in workspace
    file_name_ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"neptune_apex-json.{file_name_ts}"
    shutil.make_archive(os.path.join(workspace_directory, file_name), format='zip', root_dir=temp_files_folder)

    # Remove Workspace Lock and Provide Download
    os.remove(workspace_directory + "/WORKSPACE_LOCKED")
    return FileResponse(os.path.join(workspace_directory, f"{file_name}.zip"), media_type='application/octet-stream', filename=f"{file_name}.zip")

@app.get("/export/fusion/", response_class=PlainTextResponse, tags=["Export Fusion JSON Files"])
async def export_fusion_json(fusion_apex_id):
    """
    Export Fusion JSON data.
    Args:
        fusion_apex_id (str): The ID of the Fusion Apex.
    Returns:
        FileResponse: The response containing the exported JSON data in a zip file.
    Raises:
        FileNotFoundError: If the workspace directory or any required files are not found.
        Exception: If the workspace is locked or an error occurs during the export process.
    """

    # Defining Work Space
    workspace_directory = os.path.join(os.path.dirname(__file__), "workspace")

    # Check Workspace Lock / Lock Workspace
    if is_file_older_than(workspace_directory + "/WORKSPACE_LOCKED", datetime.timedelta(seconds=300)) == False or os.path.isfile(workspace_directory + "WORKSPACE_LOCKED") == True:
        return "Export Workspace Locked. Please run 1 export at a time.\nIf an error occurred and the lock is still in place. Wait 5 minutes and try again."

    # Cleaning Work Space
    clean_workspace()

    # Locking Workspace
    with open(os.path.join(workspace_directory, "WORKSPACE_LOCKED"), "w") as lock_file:
        lock_file.close()

    # Creating JSON Folder
    temp_files_folder = os.path.join(workspace_directory, "temp_files")
    if os.path.isdir(temp_files_folder) == False:
        os.mkdir(temp_files_folder)

    # Setting up Neptune Fusion Class in Debug Mode
    neptune_fusion_direct = neptune_fusion.FUSION(fusion_apex_id, 31536000, fusion_debug=True)

    # Measurement Log JSON
    with open(os.path.join(temp_files_folder, "mlog.json"), "w") as data_file:
        json.dump(neptune_fusion_direct.get_measurement_log(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # Status JSON
    with open(os.path.join(temp_files_folder, "status.json"), "w") as data_file:
        json.dump(neptune_fusion_direct.get_status(), data_file, indent=4, sort_keys=True)
        data_file.close()

    # Compress files in workspace/temp_files. Zip is located in workspace
    file_name_ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"neptune_fusion-json.{file_name_ts}"
    shutil.make_archive(os.path.join(workspace_directory, file_name), format='zip', root_dir=workspace_directory)

    # Remove Workspace Lock and Provide Download
    os.remove(workspace_directory + "/WORKSPACE_LOCKED")
    return FileResponse(os.path.join(workspace_directory, f"{file_name}.zip"), media_type='application/octet-stream', filename=f"{file_name}.zip")

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
