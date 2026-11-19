#!/usr/bin/python3
"""Use GNOME's existing Settings contrast control at 1x, with reversible setup.

Run as the desktop user, without sudo. This changes only magnifier preferences;
it never writes panel brightness, DRM properties, Night Light or color profiles.
No arguments reads status. Device acceptance is separate from configuration.
"""

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import sys

from gi.repository import Gio, GLib


MAG = "org.gnome.desktop.a11y.magnifier"
APP = "org.gnome.desktop.a11y.applications"
ENABLED = (APP, "screen-magnifier-enabled")
NEUTRAL = {
    (MAG, "mag-factor"): ("d", 1.0),
    (MAG, "screen-position"): ("s", "full-screen"),
    (MAG, "lens-mode"): ("b", False),
    (MAG, "scroll-at-edges"): ("b", False),
    (MAG, "show-cross-hairs"): ("b", False),
    (MAG, "invert-lightness"): ("b", False),
    (MAG, "color-saturation"): ("d", 1.0),
    **{(MAG, f"brightness-{c}"): ("d", 0.0) for c in ("red", "green", "blue")},
    **{(MAG, f"contrast-{c}"): ("d", 0.0) for c in ("red", "green", "blue")},
    ENABLED: ("b", True),
}


class Preferences:
    def __init__(self):
        source = Gio.SettingsSchemaSource.get_default()
        self.settings = {}
        self.schemas = {}
        for name in (MAG, APP):
            schema = source.lookup(name, True) if source else None
            if schema is None:
                raise RuntimeError(f"Required GNOME schema is missing: {name}")
            self.schemas[name] = schema
            self.settings[name] = Gio.Settings.new_full(schema, None, None)
        for schema, key in NEUTRAL:
            if not self.schemas[schema].has_key(key):
                raise RuntimeError(f"Required GNOME setting is missing: {key}")

    def get(self, item):
        return self.settings[item[0]].get_value(item[1])

    def validate(self, item, value):
        key = self.schemas[item[0]].get_key(item[1])
        if not value.is_of_type(key.get_value_type()) or not key.range_check(value):
            raise RuntimeError(f"Invalid saved value for {item[1]}")
        if not self.settings[item[0]].is_writable(item[1]):
            raise RuntimeError(f"GNOME setting is locked: {item[1]}")

    def write(self, item, value):
        settings = self.settings[item[0]]
        if value is None:
            settings.reset(item[1])
        elif not settings.set_value(item[1], value):
            raise RuntimeError(f"GNOME rejected setting: {item[1]}")
        Gio.Settings.sync()
        actual = settings.get_user_value(item[1])
        if (value is None and actual is not None) or (
            value is not None and not self.get(item).equal(value)
        ):
            raise RuntimeError(f"GNOME did not retain setting: {item[1]}")

    def snapshot(self):
        return [
            {"schema": schema, "key": key,
             "user_value": value.print_(True) if value is not None else None}
            for schema, key in NEUTRAL
            for value in [self.settings[schema].get_user_value(key)]
        ]


def contrast_value(text):
    value = float(text)
    if not math.isfinite(value) or not -0.75 <= value <= 0.75:
        raise argparse.ArgumentTypeError("Contrast must be between -0.75 and 0.75")
    return value


def save_snapshot(path, prefs):
    # Exclusive creation preserves the original snapshot across repeated calls.
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump({"version": 1, "uid": os.getuid(), "settings": prefs.snapshot()}, stream)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def restore_snapshot(path, prefs):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("uid") != os.getuid():
        raise RuntimeError("Snapshot belongs to another user or unsupported version")
    values = {}
    for entry in data["settings"]:
        item = (entry["schema"], entry["key"])
        if item not in NEUTRAL or item in values:
            raise RuntimeError("Unexpected or duplicate setting in snapshot")
        text = entry["user_value"]
        value = GLib.Variant.parse(None, text, None, None) if text is not None else None
        # Validate the effective default as well when restoring an unset key.
        prefs.validate(item, value if value is not None else
                       prefs.settings[item[0]].get_default_value(item[1]))
        values[item] = value
    if set(values) != set(NEUTRAL):
        raise RuntimeError("Snapshot is incomplete; no preferences changed")
    prefs.write(ENABLED, GLib.Variant("b", False))
    for item, value in values.items():
        if item != ENABLED:
            prefs.write(item, value)
    prefs.write(ENABLED, values[ENABLED])
    path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--enable", action="store_true", help="save preferences and enable 1x contrast")
    actions.add_argument("--restore", action="store_true", help="restore original magnifier preferences")
    actions.add_argument("--set", type=contrast_value, metavar="VALUE", help="adjust configured contrast")
    args = parser.parse_args()
    prefs = Preferences()
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    path = base / "j706f-screen-contrast" / "original-settings.json"
    mutation = args.enable or args.restore or args.set is not None
    if not mutation:
        print(json.dumps({"enabled": prefs.get(ENABLED).unpack(),
                          "magnification": prefs.get((MAG, "mag-factor")).unpack(),
                          "contrast": {c: prefs.get((MAG, f"contrast-{c}")).unpack()
                                       for c in ("red", "green", "blue")},
                          "restore_available": path.exists()}, indent=2))
        return
    if os.geteuid() == 0 or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        raise RuntimeError("Run as the logged-in desktop user, without sudo")
    if args.enable and (os.environ.get("XDG_SESSION_TYPE") != "wayland" or
                        "GNOME" not in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()):
        raise RuntimeError("Enable this prototype only in the GNOME Wayland desktop session")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (path.parent / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.restore:
            restore_snapshot(path, prefs)
            print("Original magnifier preferences restored.")
            return
        if args.enable:
            if path.exists():
                raise RuntimeError("Original preferences already saved; restore before enabling again")
            if prefs.get(ENABLED).unpack():
                raise RuntimeError("Desktop Zoom is already in use; use its existing Settings controls")
            for item, (kind, value) in NEUTRAL.items():
                prefs.validate(item, GLib.Variant(kind, value))
            save_snapshot(path, prefs)
            # Enable last so the first displayed frame uses neutral 1x settings.
            for item, (kind, value) in NEUTRAL.items():
                prefs.write(item, GLib.Variant(kind, value))
            print("Configured 1x contrast. Open Settings → Accessibility → Zoom → Color Filters.")
            print("Visual behavior and performance still require validation on this device.")
        else:
            if not path.exists() or not prefs.get(ENABLED).unpack():
                raise RuntimeError("Enable the reversible 1x setup before setting contrast")
            if prefs.get((MAG, "mag-factor")).unpack() != 1.0:
                raise RuntimeError("Magnification was changed; use Settings or restore the saved setup")
            for color in ("red", "green", "blue"):
                prefs.write((MAG, f"contrast-{color}"), GLib.Variant("d", args.set))
            print("Contrast preference updated; confirm the picture visually.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, GLib.Error) as error:
        print(f"screen-contrast: {error}", file=sys.stderr)
        print("If setup changed any preferences, --restore uses the saved originals.", file=sys.stderr)
        sys.exit(1)
