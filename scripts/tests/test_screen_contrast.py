"""Recovery checks using Gio's isolated memory backend, never the desktop dconf."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["GSETTINGS_BACKEND"] = "memory"
spec = importlib.util.spec_from_file_location(
    "screen_contrast", Path(__file__).parents[1] / "screen-contrast.py")
contrast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contrast)
from gi.repository import GLib  # noqa: E402


class RestorePreferences(unittest.TestCase):
    def setUp(self):
        self.prefs = contrast.Preferences()
        for schema, key in contrast.NEUTRAL:
            self.prefs.settings[schema].reset(key)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "original.json"

    def test_restore_preserves_explicit_values_and_unset_defaults(self):
        item = (contrast.MAG, "mag-factor")
        self.prefs.write(item, GLib.Variant("d", 3.5))
        before = self.prefs.snapshot()
        contrast.save_snapshot(self.path, self.prefs)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        for key, (kind, value) in contrast.NEUTRAL.items():
            self.prefs.write(key, GLib.Variant(kind, value))
        self.prefs.write((contrast.MAG, "contrast-red"), GLib.Variant("d", 0.3))
        contrast.restore_snapshot(self.path, self.prefs)
        self.assertEqual(self.prefs.snapshot(), before)
        self.assertFalse(self.path.exists())

    def test_original_backup_cannot_be_overwritten(self):
        contrast.save_snapshot(self.path, self.prefs)
        original = self.path.read_bytes()
        self.prefs.write((contrast.MAG, "mag-factor"), GLib.Variant("d", 1.0))
        with self.assertRaises(FileExistsError):
            contrast.save_snapshot(self.path, self.prefs)
        self.assertEqual(self.path.read_bytes(), original)

    def test_incomplete_backup_rejected_before_writes(self):
        contrast.save_snapshot(self.path, self.prefs)
        data = json.loads(self.path.read_text())
        data["settings"].pop()
        self.path.write_text(json.dumps(data))
        before = self.prefs.snapshot()
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            contrast.restore_snapshot(self.path, self.prefs)
        self.assertEqual(self.prefs.snapshot(), before)
        self.assertTrue(self.path.exists())

    def test_interrupted_restore_retains_backup_for_retry(self):
        contrast.save_snapshot(self.path, self.prefs)
        before = self.prefs.snapshot()
        for key, (kind, value) in contrast.NEUTRAL.items():
            self.prefs.write(key, GLib.Variant(kind, value))
        original_write = self.prefs.write
        calls = 0

        def failing_write(item, value):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError("simulated interrupted restore")
            original_write(item, value)

        self.prefs.write = failing_write
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            contrast.restore_snapshot(self.path, self.prefs)
        self.assertTrue(self.path.exists())
        self.prefs.write = original_write
        contrast.restore_snapshot(self.path, self.prefs)
        self.assertEqual(self.prefs.snapshot(), before)

    def test_invalid_backup_range_rejected_before_writes(self):
        contrast.save_snapshot(self.path, self.prefs)
        data = json.loads(self.path.read_text())
        data["settings"][0]["user_value"] = "999.0"
        self.path.write_text(json.dumps(data))
        before = self.prefs.snapshot()
        with self.assertRaisesRegex(RuntimeError, "Invalid saved value"):
            contrast.restore_snapshot(self.path, self.prefs)
        self.assertEqual(self.prefs.snapshot(), before)

    def test_enable_adjust_restore_in_isolated_backend(self):
        before = self.prefs.snapshot()
        env = {"XDG_STATE_HOME": self.tmp.name, "XDG_CURRENT_DESKTOP": "GNOME",
               "XDG_SESSION_TYPE": "wayland", "DBUS_SESSION_BUS_ADDRESS": "memory-test"}
        with patch.dict(os.environ, env), patch.object(os, "geteuid", return_value=1000):
            for arguments in (("--enable",), ("--set", "0.2"), ("--restore",)):
                with patch("sys.argv", ["screen-contrast", *arguments]):
                    contrast.main()
                if arguments[0] == "--set":
                    for color in ("red", "green", "blue"):
                        self.assertAlmostEqual(self.prefs.get(
                            (contrast.MAG, f"contrast-{color}")).unpack(), 0.2)
        self.assertEqual(self.prefs.snapshot(), before)

    def test_existing_accessibility_zoom_is_not_reconfigured(self):
        self.prefs.write(contrast.ENABLED, GLib.Variant("b", True))
        before = self.prefs.snapshot()
        env = {"XDG_STATE_HOME": self.tmp.name, "XDG_CURRENT_DESKTOP": "GNOME",
               "XDG_SESSION_TYPE": "wayland", "DBUS_SESSION_BUS_ADDRESS": "memory-test"}
        with patch.dict(os.environ, env), patch.object(os, "geteuid", return_value=1000), \
                patch("sys.argv", ["screen-contrast", "--enable"]):
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                contrast.main()
        self.assertEqual(self.prefs.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
