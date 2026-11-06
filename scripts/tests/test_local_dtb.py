"""Synthetic DTB tests; no device, private config or kernel build is used."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(all(shutil.which(command) for command in ("dtc", "fdtget", "fdtput")),
                     "device-tree-compiler tools are required")
class LocalDtbConfiguration(unittest.TestCase):
    def setUp(self):
        build = Path(os.environ.get("J706F_BUILD_ROOT", ROOT.parent / "j706f-build"))
        build.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="local-dtb-test-", dir=build)
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.config = self.work / "config"
        self.config.mkdir()
        self.dtb = self.work / "synthetic.dtb"
        self.dts = self.work / "synthetic.dts"
        self.env = dict(os.environ, J706F_CONFIG_DIR=str(self.config), PYTHONDONTWRITEBYTECODE="1")
        self.set_config(None)
        self.compile()

    def compile(self, *, symbol=True, bluetooth=True):
        # Explicitly synthetic identities; neither fixture comes from a device.
        label = "uart3: " if symbol else ""
        child = 'bluetooth { compatible = "qcom,wcn3998-bt"; local-bd-address = [01 02 03 04 05 02]; };' if bluetooth else ""
        self.dts.write_text(f"/dts-v1/; / {{ {label}serial {{ {child} }}; }};\n")
        subprocess.run(["dtc", "-@", "-I", "dts", "-O", "dtb", "-o", self.dtb, self.dts],
                       check=True, capture_output=True)

    def set_config(self, value):
        (self.config / "bluetooth.json").write_text(json.dumps({"local_bd_address_le": value}))

    def execute(self, path=None):
        return subprocess.run([sys.executable, ROOT / "scripts/apply-local-dtb.py",
                               "--dtb", path or self.dtb], env=self.env,
                              capture_output=True, text=True)

    def properties(self):
        return subprocess.check_output(["fdtget", "-p", self.dtb, "/serial/bluetooth"], text=True).splitlines()

    def test_null_and_removed_configuration_clear_previous_generated_identity(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"local_bluetooth_identity_applied": False})
        self.assertNotIn("local-bd-address", self.properties())
        self.set_config("10 20 30 40 50 02")
        self.assertEqual(self.execute().returncode, 0)
        (self.config / "bluetooth.json").unlink()
        self.assertEqual(self.execute().returncode, 0)
        self.assertNotIn("local-bd-address", self.properties())

    def test_configured_identity_is_written_and_not_printed(self):
        value = "10 20 30 40 50 02"
        self.set_config(value)
        source = self.dts.read_bytes()
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"local_bluetooth_identity_applied": True})
        actual = subprocess.check_output(
            ["fdtget", "-t", "bx", self.dtb, "/serial/bluetooth", "local-bd-address"], text=True)
        self.assertEqual(bytes(int(part, 16) for part in actual.split()), bytes.fromhex(value))
        self.assertNotIn(value, result.stdout + result.stderr)
        self.assertEqual(source, self.dts.read_bytes())

    def test_invalid_identity_fails_without_replacing_input_or_logging_value(self):
        for value in ("00 00 00 00 00 00", "ff ff ff ff ff ff", "10 20 30 40 50 01",
                      "01 02", "not-an-address", [1, 2, 3, 4, 5, 2]):
            with self.subTest(value_type=type(value).__name__):
                self.set_config(value)
                original = self.dtb.read_bytes()
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(original, self.dtb.read_bytes())
                if isinstance(value, str):
                    self.assertNotIn(value, result.stdout + result.stderr)

    def test_missing_symbol_or_bluetooth_node_fails_without_changes(self):
        for options in ({"symbol": False}, {"bluetooth": False}):
            with self.subTest(options=options):
                self.compile(**options)
                original = self.dtb.read_bytes()
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(original, self.dtb.read_bytes())

    def test_checkout_path_is_rejected(self):
        result = self.execute(ROOT / "configs/bluetooth.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the source checkout", result.stderr)


if __name__ == "__main__":
    unittest.main()
