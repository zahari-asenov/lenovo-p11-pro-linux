#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply optional private Bluetooth identity only to an external generated DTB.

Never prints the configured address. A missing/null setting removes stale local
identity from a previously generated DTB. Invalid configuration fails without
replacing the input; callers must stop the build on a nonzero exit status.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from project_config import PROJECT_ROOT, load_config


def address_bytes(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
            r"[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2}){5}", value.strip()):
        raise ValueError("Bluetooth identity must be six whitespace-separated hexadecimal bytes")
    address = bytes.fromhex(value)
    # The most significant address octet is last in this DT property's LE form.
    if address in (bytes(6), bytes([255]) * 6) or address[-1] & 1:
        raise ValueError("Bluetooth identity must be nonzero, non-broadcast and unicast")
    return address


def tool(command, operation):
    # Do not relay command arguments or tool output: either may contain identity.
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Device-tree tool failed while {operation}")
    return result.stdout.strip()


def apply(dtb, address):
    path = dtb.expanduser().resolve(strict=True)
    if path.is_relative_to(PROJECT_ROOT):
        raise ValueError("DTB must be generated outside the source checkout")
    if not stat.S_ISREG(path.stat().st_mode) or path.suffix != ".dtb":
        raise ValueError("Expected a regular external .dtb file")
    mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.TemporaryDirectory(prefix="local-dtb-", dir=path.parent) as temporary:
        candidate = Path(temporary) / "candidate.dtb"
        shutil.copyfile(path, candidate)
        uart = tool(["fdtget", "-t", "s", str(candidate), "/__symbols__", "uart3"],
                    "resolving the UART3 symbol")
        if not uart.startswith("/") or any(c.isspace() for c in uart) or ".." in uart.split("/"):
            raise ValueError("Unexpected UART3 symbol path")
        node = uart.rstrip("/") + "/bluetooth"
        properties = tool(["fdtget", "-p", str(candidate), node],
                          "reading Bluetooth node properties").splitlines()
        if "local-bd-address" in properties:
            tool(["fdtput", "-d", str(candidate), node, "local-bd-address"],
                 "clearing the previous local Bluetooth identity")
        if address is not None:
            tool(["fdtput", "-t", "bx", str(candidate), node, "local-bd-address",
                  *(f"{byte:02x}" for byte in address)], "applying the local Bluetooth identity")
            actual = tool(["fdtget", "-t", "bx", str(candidate), node, "local-bd-address"],
                          "verifying the local Bluetooth identity")
            if bytes(int(byte, 16) for byte in actual.split()) != address:
                raise RuntimeError("Local Bluetooth identity readback failed")
        else:
            properties = tool(["fdtget", "-p", str(candidate), node],
                              "verifying local Bluetooth identity removal").splitlines()
            if "local-bd-address" in properties:
                raise RuntimeError("Local Bluetooth identity removal failed")
        os.chmod(candidate, mode)
        with candidate.open("rb") as stream:
            os.fsync(stream.fileno())
        candidate.replace(path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dtb", required=True, type=Path)
    args = parser.parse_args()
    for command in ("fdtget", "fdtput"):
        if not shutil.which(command):
            raise RuntimeError("Install device-tree-compiler to configure the generated DTB")
    address = address_bytes(load_config("bluetooth").get("local_bd_address_le"))
    apply(args.dtb, address)
    print(json.dumps({"local_bluetooth_identity_applied": address is not None}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Local DTB configuration failed: {error}", file=sys.stderr)
        sys.exit(1)
