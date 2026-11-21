"""Configuration isolation and fail-closed identity checks; no device inputs."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "project_config", Path(__file__).parents[1] / "project_config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ProjectConfiguration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "configs"
        (self.directory / "local").mkdir(parents=True)
        self.template = {"serial": "CONFIGURE_DEVICE_SERIAL",
                         "partuuid": "00000000-0000-0000-0000-000000000000",
                         "partname": "userdata", "bytes": 65536, "sectors_512": 128,
                         "boot_bytes": 67108864, "root_id": "CONFIGURE_EXISTING_ROOT_MARKER",
                         "nested": {"retained": True}}
        (self.directory / "persistent.json").write_text(json.dumps(self.template))
        self.patch = patch.object(config, "CONFIG_ROOT", self.directory)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.environment = patch.dict(os.environ, {}, clear=False)
        self.environment.start()
        os.environ.pop("J706F_CONFIG_DIR", None)
        self.addCleanup(self.environment.stop)

    def configured(self, serial="TEST-DEVICE"):
        value = copy.deepcopy(self.template)
        value.update(serial=serial, partuuid="11111111-2222-4333-8444-555555555555")
        value["root_id"] = f"J706F-PERSISTENT-V1:{serial}:{value['partuuid']}"
        return value

    def test_template_loads_for_host_tests_but_device_use_is_rejected(self):
        self.assertEqual(config.load_config("persistent"), self.template)
        with self.assertRaisesRegex(ValueError, "device serial"):
            config.load_config("persistent", require_device=True)

    def test_local_merge_retains_unspecified_defaults(self):
        local = self.configured()
        local.pop("bytes")
        local["nested"] = {"added": 42}
        (self.directory / "local/persistent.json").write_text(json.dumps(local))
        actual = config.load_config("persistent.json", require_device=True)
        self.assertEqual(actual["bytes"], 65536)
        self.assertEqual(actual["nested"], {"retained": True, "added": 42})

    def test_explicit_environment_directory_does_not_mix_default_local_file(self):
        (self.directory / "local/persistent.json").write_text(json.dumps(self.configured("TEST-LOCAL")))
        external = Path(self.tmp.name) / "external"
        external.mkdir()
        (external / "persistent.json").write_text(json.dumps(self.configured("TEST-EXTERNAL")))
        os.environ["J706F_CONFIG_DIR"] = str(external)
        self.assertEqual(config.load_config("persistent", require_device=True)["serial"], "TEST-EXTERNAL")

    def test_empty_explicit_directory_never_falls_back_to_private_local_identity(self):
        (self.directory / "local/persistent.json").write_text(json.dumps(self.configured("TEST-LOCAL")))
        external = Path(self.tmp.name) / "empty"
        external.mkdir()
        os.environ["J706F_CONFIG_DIR"] = str(external)
        self.assertEqual(config.load_config("persistent"), self.template)
        with self.assertRaisesRegex(ValueError, "device serial"):
            config.load_config("persistent", require_device=True)

    def test_explicit_runtime_config_is_validated_without_overlay(self):
        path = Path(self.tmp.name) / "device.json"
        path.write_text(json.dumps(self.configured()))
        self.assertEqual(config.load_device_config(path), self.configured())
        path.write_text(json.dumps(self.template))
        with self.assertRaises(ValueError):
            config.load_device_config(path)

    def test_identity_geometry_marker_and_shell_injection_are_rejected(self):
        for field, value in (("partuuid", "00000000-0000-0000-0000-000000000000"),
                             ("serial", "BAD'$(echo injected)"), ("root_id", "wrong"),
                             ("bytes", 65537), ("sectors_512", True),
                             ("boot_bytes", 1), ("partname", "other")):
            with self.subTest(field=field):
                plan = self.configured()
                plan[field] = value
                with self.assertRaises(ValueError):
                    config.shell_root_config(plan)

    def test_config_filename_cannot_escape_directory(self):
        for name in ("../private", "nested/config", "/tmp/persistent"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                config.load_config(name)

    def test_generated_shell_identity_roundtrips_and_covers_consumers(self):
        plan = self.configured()
        data = config.shell_root_config(plan)
        generated = {line.split("=", 1)[0] for line in data.decode().splitlines()}
        root = Path(__file__).resolve().parents[2]
        for relative in ("bootstrap/init-persistent", "bootstrap/maintenance-check.sh",
                         "scripts/repair-root-offline.sh"):
            variables = set(re.findall(r"\$(?:\{)?(J706F_[A-Z0-9_]+)",
                                       (root / relative).read_text()))
            self.assertTrue(variables <= generated, relative)
        identity = Path(self.tmp.name) / "root.conf"
        identity.write_bytes(data)
        fields = ("J706F_SERIAL", "J706F_PARTUUID", "J706F_SECTORS", "J706F_BYTES",
                  "J706F_PARTNAME", "J706F_ROOT_ID")
        command = '. "$1"; printf \'%s\\n\' ' + " ".join(f'"${field}"' for field in fields)
        result = subprocess.run(["sh", "-eu", "-c", command, "identity-check", identity],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), [plan["serial"], plan["partuuid"],
                         str(plan["sectors_512"]), str(plan["bytes"]), plan["partname"], plan["root_id"]])


if __name__ == "__main__":
    unittest.main()
