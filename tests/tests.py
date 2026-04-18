import asyncio
import json
import shutil
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import neptune_exporter


class DummyApex:
    def __init__(self, apex_ip, auth_module, apex_debug=False):
        self.apex_ip = apex_ip
        self.auth_module = auth_module
        self.apex_debug = apex_debug

    def status(self):
        return {"status": "ok"}

    def internal_log(self):
        return {"ilog": True}

    def dos_log(self):
        return {"dlog": True}

    def trident_log(self):
        return {"tlog": True}

    def config(self):
        return {"config": True}


class NeptuneExporterTests(unittest.TestCase):
    def setUp(self):
        self.workspace_dir = Path(neptune_exporter.__file__).resolve().parent / "workspace"
        self.workspace_dir.mkdir(exist_ok=True)
        lock_file = self.workspace_dir / "WORKSPACE_LOCKED"
        if lock_file.exists():
            lock_file.unlink()

    def tearDown(self):
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)

    def test_health_endpoint_reports_ok(self):
        result = asyncio.run(neptune_exporter.health_check())
        self.assertEqual(result["status"], "ok")

    @patch("neptune_exporter.neptune_apex.APEX", DummyApex)
    def test_export_apex_json_succeeds_without_existing_lock(self):
        response = asyncio.run(
            neptune_exporter.export_apex_json(target="127.0.0.1", auth_module="default")
        )

        self.assertEqual(response.status_code, 200)
        archive_path = Path(response.path)
        self.assertTrue(archive_path.exists())

        with zipfile.ZipFile(archive_path, "r") as archive:
            config_payload = json.loads(archive.read("config.json"))

        self.assertEqual(config_payload, {"config": True})


if __name__ == "__main__":
    unittest.main()
