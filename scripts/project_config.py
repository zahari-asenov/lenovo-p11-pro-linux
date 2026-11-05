#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tracked configuration templates plus optional, ignored local overrides.

Device-specific tools must request validation before reading device inputs.
Ordinary host tests may load the unconfigured templates without device access.
"""

import copy
import json
import os
from pathlib import Path
import re
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "configs"


def build_root():
    return Path(os.environ.get("J706F_BUILD_ROOT", PROJECT_ROOT.parent / "j706f-build")).expanduser().resolve()


def _read_object(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a JSON object: {path}")
    return data


def _merge(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def configured_serial(config):
    serial = config.get("serial")
    if (not isinstance(serial, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{3,63}", serial)
            or serial.upper().startswith(("CONFIGURE", "EXAMPLE", "PLACEHOLDER"))):
        raise ValueError("Configure the device serial in a private local JSON file before device operations")
    return serial


def validate_device_config(config):
    """Validate this model's existing userdata-root plan, never infer identity."""
    serial = configured_serial(config)
    try:
        partuuid = uuid.UUID(config["partuuid"])
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValueError("Configure the existing root partition UUID") from error
    if not partuuid.int:
        raise ValueError("The all-zero template partition UUID is not a device identity")
    if str(partuuid) != config["partuuid"]:
        raise ValueError("Use the canonical lowercase partition UUID")
    if config.get("partname") != "userdata":
        raise ValueError("This helper only supports the reviewed userdata-root layout")
    size, sectors = config.get("bytes"), config.get("sectors_512")
    if (type(size) is not int or type(sectors) is not int or sectors <= 0
            or size != sectors * 512):
        raise ValueError("Configure matching positive root bytes and 512-byte sectors")
    if config.get("boot_bytes") != 64 * 1024 * 1024:
        raise ValueError("This helper requires the reviewed 64 MiB boot partition layout")
    expected = f"J706F-PERSISTENT-V1:{serial}:{partuuid}"
    if config.get("root_id") != expected:
        raise ValueError("Configure the exact existing root marker matching serial and partition UUID")
    return config


def load_config(name, *, require_device=False):
    """Merge configs/NAME.json with local/NAME.json (or J706F_CONFIG_DIR/NAME.json)."""
    name = name.removesuffix(".json")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("Configuration name must be a simple filename")
    filename = name + ".json"
    result = _read_object(CONFIG_ROOT / filename)
    local = Path(os.environ.get("J706F_CONFIG_DIR", CONFIG_ROOT / "local")).expanduser() / filename
    if local.exists():
        result = _merge(result, _read_object(local))
    if require_device:
        if name == "persistent":
            validate_device_config(result)
        else:
            configured_serial(result)
    return result


def load_device_config(path):
    """Load one explicit runtime plan, without guessing a device or local file."""
    return validate_device_config(_read_object(path))


def shell_root_config(plan):
    """Validated values safe for a single-quoted initramfs identity configuration."""
    validate_device_config(plan)
    values = {"J706F_SERIAL": plan["serial"], "J706F_PARTUUID": plan["partuuid"],
              "J706F_SECTORS": str(plan["sectors_512"]), "J706F_BYTES": str(plan["bytes"]),
              "J706F_PARTNAME": plan["partname"], "J706F_ROOT_ID": plan["root_id"]}
    return "".join(f"{key}='{value}'\n" for key, value in values.items()).encode()
