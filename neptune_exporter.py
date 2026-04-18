"""Neptune Apex Exporter for Prometheus."""

import datetime
import json
import logging
import os
import shutil
from contextlib import contextmanager
from ipaddress import ip_address
from pathlib import Path
from typing import Iterator

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.responses import FileResponse

from neptune_modules import neptune_apex
from neptune_modules import neptune_fusion

UTC = datetime.timezone.utc

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "configuration"
LOG_DIR = BASE_DIR / "logs"
WORKSPACE_DIR = BASE_DIR / "workspace"

LOG_DIR.mkdir(exist_ok=True)
WORKSPACE_DIR.mkdir(exist_ok=True)


def setup_logger(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """Set up the logger for the application."""
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


application_logger = setup_logger("neptune_exporter", LOG_DIR / "exporter.log")


def load_yaml_config(config_path: Path) -> dict:
    """Load a YAML config file safely."""
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            loaded_config = yaml.safe_load(config_file) or {}
    except FileNotFoundError as exc:
        raise RuntimeError(f"Configuration file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in configuration file: {config_path}") from exc

    if not isinstance(loaded_config, dict):
        raise RuntimeError(f"Configuration must be a mapping: {config_path}")

    return loaded_config


try:
    configuration = load_yaml_config(CONFIG_DIR / "exporter.yml")
except RuntimeError as exc:
    application_logger.exception("Configuration File Load Failed: %s", exc)
    raise SystemExit(1) from exc

exporter_info = configuration.get("neptune_exporter", {})

app = FastAPI(
    title=exporter_info.get("title", "Neptune Exporter"),
    summary=exporter_info.get("summary", "Prometheus Exporter for the Neptune Apex."),
    description=exporter_info.get("description", "https://github.com/dl-romero/neptune_exporter"),
    version=str(exporter_info.get("version", "1.0")),
    contact=exporter_info.get(
        "contact",
        {
            "name": "dromero.dev",
            "url": "https://dromero.dev",
        },
    ),
    license_info=exporter_info.get(
        "license_info",
        {
            "name": "License",
            "url": "https://github.com/dl-romero/neptune_exporter/blob/main/LICENSE",
        },
    ),
    openapi_tags=[
        {
            "name": "Health",
            "description": "Service health endpoints.",
        },
        {
            "name": "Apex",
            "description": "Get Apex metrics in Prometheus format.",
        },
        {
            "name": "Fusion",
            "description": "Get Fusion metrics in Prometheus format.",
        },
        {
            "name": "Export Logs",
            "description": "Download Neptune Exporter log data.",
        },
        {
            "name": "Export Apex JSON Files",
            "description": "Download Apex JSON data.",
        },
        {
            "name": "Export Fusion JSON Files",
            "description": "Download Fusion JSON data.",
        },
    ],
)


def clean_workspace() -> bool:
    """Remove all generated workspace content while preserving the lock file."""
    WORKSPACE_DIR.mkdir(exist_ok=True)
    for item in WORKSPACE_DIR.iterdir():
        if item.name == "WORKSPACE_LOCKED":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    return True


def is_file_older_than(file_path: Path | str, delta: datetime.timedelta) -> bool:
    """Check whether a file is older than a specified time delta."""
    checked_file = Path(file_path)
    if not checked_file.exists():
        return True

    cutoff = datetime.datetime.now(UTC) - delta
    mtime = datetime.datetime.fromtimestamp(checked_file.stat().st_mtime, tz=UTC)
    return mtime < cutoff


@contextmanager
def workspace_lock() -> Iterator[Path]:
    """Lock the export workspace for a single export job."""
    WORKSPACE_DIR.mkdir(exist_ok=True)
    lock_path = WORKSPACE_DIR / "WORKSPACE_LOCKED"

    if lock_path.exists() and is_file_older_than(lock_path, datetime.timedelta(minutes=5)):
        lock_path.unlink(missing_ok=True)

    try:
        with lock_path.open("x", encoding="utf-8") as lock_file:
            lock_file.write(datetime.datetime.now(UTC).isoformat())
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="Export workspace is locked. Please wait a few minutes and try again.",
        ) from exc

    try:
        clean_workspace()
        yield WORKSPACE_DIR
    finally:
        if lock_path.exists():
            lock_path.unlink()


def validate_target(target: str) -> str:
    """Validate the target IP address for local Apex scraping."""
    try:
        return str(ip_address(target))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid target IP address.") from exc


def validate_auth_module(auth_module: str) -> str:
    """Validate the configured local Apex auth module."""
    configured_auths = neptune_apex.configuration.get("apex_auths", {})
    if auth_module not in configured_auths:
        raise HTTPException(status_code=400, detail="Invalid auth_module.")
    return auth_module


def validate_fusion_apex_id(fusion_apex_id: str) -> str:
    """Validate the configured Fusion system id."""
    configured_systems = neptune_fusion.configuration.get("fusion", {}).get("apex_systems", {})
    if fusion_apex_id not in configured_systems:
        raise HTTPException(status_code=400, detail="Invalid fusion_apex_id.")
    return fusion_apex_id


def write_json_file(output_path: Path, payload: object) -> None:
    """Write JSON data to disk with deterministic formatting."""
    with output_path.open("w", encoding="utf-8") as data_file:
        json.dump(payload, data_file, indent=4, sort_keys=True)


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness endpoint for service and container health checks."""
    return {
        "status": "ok",
        "service": "neptune_exporter",
        "time_utc": datetime.datetime.now(UTC).isoformat(),
    }


@app.get("/metrics/apex", response_class=PlainTextResponse, tags=["Apex"])
async def apex_prometheus_metrics(
    target: str = Query(..., description="The IP address of the Apex device."),
    auth_module: str = Query(..., min_length=1, max_length=100),
):
    """Get Apex metrics in Prometheus format."""
    validated_target = validate_target(target)
    validated_auth_module = validate_auth_module(auth_module)

    try:
        apex_direct = neptune_apex.APEX(apex_ip=validated_target, auth_module=validated_auth_module)
        metrics = apex_direct.prometheus_metrics()
    except HTTPException:
        raise
    except Exception as exc:
        application_logger.exception("Apex metrics collection failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to collect Apex metrics.") from exc

    return metrics


@app.get("/metrics/fusion", response_class=PlainTextResponse, tags=["Fusion"])
async def fusion_prometheus_metrics(
    data_max_age: int = Query(..., ge=60, le=86400),
    fusion_apex_id: str = Query(..., min_length=1, max_length=128),
):
    """Get Fusion metrics in Prometheus format."""
    validated_fusion_apex_id = validate_fusion_apex_id(fusion_apex_id)

    try:
        with neptune_fusion.FUSION(validated_fusion_apex_id, data_max_age) as apex_fusion:
            metrics = apex_fusion.prometheus_metrics()
    except HTTPException:
        raise
    except Exception as exc:
        application_logger.exception("Fusion metrics collection failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to collect Fusion metrics.") from exc

    return metrics


@app.get("/export/logs/", tags=["Export Log Data"])
async def apex_exporter_logs():
    """Export and download application logs."""
    archive_path = None

    with workspace_lock() as workspace_directory:
        file_name_ts = datetime.datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        archive_base = workspace_directory / f"neptune_exporter-logs.{file_name_ts}"
        shutil.make_archive(str(archive_base), format="zip", root_dir=LOG_DIR)
        archive_path = Path(f"{archive_base}.zip")

    return FileResponse(
        path=str(archive_path),
        media_type="application/octet-stream",
        filename=archive_path.name,
    )


@app.get("/export/apex/", tags=["Export Apex JSON Files"])
async def export_apex_json(
    target: str = Query(..., description="The IP address of the Apex device."),
    auth_module: str = Query(..., min_length=1, max_length=100),
):
    """Export Apex JSON data from a Neptune Apex device."""
    validated_target = validate_target(target)
    validated_auth_module = validate_auth_module(auth_module)

    with workspace_lock() as workspace_directory:
        temp_files_folder = workspace_directory / "temp_files"
        temp_files_folder.mkdir(exist_ok=True)

        apex_direct = neptune_apex.APEX(
            apex_ip=validated_target,
            auth_module=validated_auth_module,
            apex_debug=True,
        )

        payloads = {
            "status.json": apex_direct.status(),
            "ilog.json": apex_direct.internal_log(),
            "dlog.json": apex_direct.dos_log(),
            "tlog.json": apex_direct.trident_log(),
            "config.json": apex_direct.config(),
        }
        for file_name, payload in payloads.items():
            write_json_file(temp_files_folder / file_name, payload)

        file_name_ts = datetime.datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        archive_base = workspace_directory / f"neptune_apex-json.{file_name_ts}"
        shutil.make_archive(str(archive_base), format="zip", root_dir=temp_files_folder)
        archive_path = Path(f"{archive_base}.zip")

    return FileResponse(
        path=str(archive_path),
        media_type="application/octet-stream",
        filename=archive_path.name,
    )


@app.get("/export/fusion/", tags=["Export Fusion JSON Files"])
async def export_fusion_json(
    fusion_apex_id: str = Query(..., min_length=1, max_length=128),
):
    """Export Fusion JSON data."""
    validated_fusion_apex_id = validate_fusion_apex_id(fusion_apex_id)

    with workspace_lock() as workspace_directory:
        temp_files_folder = workspace_directory / "temp_files"
        temp_files_folder.mkdir(exist_ok=True)

        with neptune_fusion.FUSION(validated_fusion_apex_id, 31536000, fusion_debug=True) as fusion_client:
            write_json_file(temp_files_folder / "mlog.json", fusion_client.get_measurement_log())
            write_json_file(temp_files_folder / "status.json", fusion_client.get_status())

        file_name_ts = datetime.datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        archive_base = workspace_directory / f"neptune_fusion-json.{file_name_ts}"
        shutil.make_archive(str(archive_base), format="zip", root_dir=temp_files_folder)
        archive_path = Path(f"{archive_base}.zip")

    return FileResponse(
        path=str(archive_path),
        media_type="application/octet-stream",
        filename=archive_path.name,
    )


@app.get("/", include_in_schema=False)
async def documentation_home_page():
    """Redirect to the documentation home page."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(
        "neptune_exporter:app",
        host=os.getenv("NEPTUNE_EXPORTER_HOST", "0.0.0.0"),
        port=int(os.getenv("NEPTUNE_EXPORTER_PORT", "5006")),
        log_level=os.getenv("NEPTUNE_EXPORTER_LOG_LEVEL", "info"),
    )
