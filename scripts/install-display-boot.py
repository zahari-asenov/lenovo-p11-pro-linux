#!/usr/bin/env python3
"""Preflight or install an explicitly authorized J706F boot-only display image.

Default: read-only JSON preflight. --apply requires that exact preflight and
rechecks both original full-partition hashes before writing boot_b then boot_a.
No backups, partition-table changes, DTBO writes or automatic reboot are made.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from project_config import load_device_config


SIZE = 64 * 1024 * 1024
CHUNK = 1024 * 1024
TARGETS = (("boot_b", "sde30"), ("boot_a", "sde11"))
DISK = Path("/dev/sde")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def blockdev(option, node):
    return subprocess.check_output(["blockdev", option, str(node)], text=True).strip()


def ro(node):
    value = blockdev("--getro", node)
    require(value in ("0", "1"), f"Invalid read-only flag for {node}")
    return int(value)


def set_ro(node, value):
    blockdev("--setro" if value else "--setrw", node)
    require(ro(node) == value, f"Read-only flag restoration/change failed: {node}")


def full_hash(node):
    digest = hashlib.sha256()
    remaining = SIZE
    with node.open("rb", buffering=0) as stream:
        while remaining:
            chunk = stream.read(min(CHUNK, remaining))
            require(bool(chunk), f"Short read from {node}")
            digest.update(chunk)
            remaining -= len(chunk)
        require(not stream.read(1), f"Unexpected oversized boot partition: {node}")
    return digest.hexdigest()


def health(plan):
    serial_tokens = [value for value in Path("/proc/cmdline").read_text().split()
                     if value.startswith("androidboot.serialno=")]
    require(serial_tokens == [f"androidboot.serialno={plan['serial']}"],
            "Unexpected or ambiguous tablet serial")
    source = subprocess.check_output(
        ["findmnt", "-n", "-o", "SOURCE", "/"], text=True).strip()
    options = subprocess.check_output(
        ["findmnt", "-n", "-o", "OPTIONS", "/"], text=True).strip().split(",")
    fstype = subprocess.check_output(
        ["findmnt", "-n", "-o", "FSTYPE", "/"], text=True).strip()
    require(source == "/dev/sda15" and fstype == "ext4", "Unexpected installed root")
    root_sys = Path("/sys/class/block/sda15")
    identity = dict(line.split("=", 1) for line in
                    (root_sys / "uevent").read_text().splitlines() if "=" in line)
    require(identity.get("PARTUUID") == plan["partuuid"] and
            identity.get("PARTNAME") == plan["partname"], "Installed root identity disagrees with device config")
    require(int((root_sys / "size").read_text()) * 512 == plan["bytes"], "Installed root size disagreement")
    require(Path("/etc/j706f-root-id").read_text().strip() == plan["root_id"], "Installed root marker disagreement")
    require("rw" in options and "ro" not in options and "emergency_ro" not in options,
            "Installed root must be writable, without emergency read-only mode")
    errors = int(Path("/sys/fs/ext4/sda15/errors_count").read_text())
    require(errors == 0, "Installed root has recorded ext4 errors")
    power = Path("/sys/class/power_supply/pm8150b-charger/online").read_text().strip()
    require(power == "1", "External power is required")
    batteries = []
    for supply in sorted(Path("/sys/class/power_supply").iterdir()):
        type_file = supply / "type"
        if not type_file.exists() or type_file.read_text().strip() != "Battery":
            continue
        capacity_file = supply / "capacity"
        if capacity_file.exists():
            capacity = int(capacity_file.read_text())
            require(30 <= capacity <= 100, f"Battery capacity unsuitable: {capacity}%")
            batteries.append({"supply": supply.name, "capacity_percent": capacity})
    return {"serial": plan["serial"], "root_partuuid": plan["partuuid"],
            "root_id": plan["root_id"], "root_source": source, "root_fstype": fstype,
            "root_rw": True, "root_ext4_errors": errors, "external_power_online": True,
            "batteries": batteries}


def inspect_targets(new_hash):
    require(stat.S_ISBLK(DISK.stat().st_mode), "Parent disk is not a block device")
    targets = []
    for name, expected_node in TARGETS:
        node = (Path("/dev/disk/by-partlabel") / name).resolve(strict=True)
        require(node == Path("/dev") / expected_node, f"Unexpected {name} device: {node}")
        require(stat.S_ISBLK(node.stat().st_mode), f"Not a block device: {node}")
        system = Path("/sys/class/block") / node.name
        require(system.resolve(strict=True).parent.name == "sde", "Unexpected parent disk")
        values = dict(line.split("=", 1) for line in
                      (system / "uevent").read_text().splitlines() if "=" in line)
        require(values.get("PARTNAME") == name, f"Unexpected sysfs PARTNAME for {node}")
        require(int((system / "size").read_text()) * 512 == SIZE,
                f"Unexpected boot partition size: {node}")
        require(int(blockdev("--getsize64", node)) == SIZE, "Block device size disagreement")
        targets.append({"target": name, "device": str(node), "parent_disk": str(DISK),
                        "size_bytes": SIZE, "original_read_only": ro(node),
                        "old_full_sha256": full_hash(node), "new_full_sha256": new_hash})
    return targets


def padded_hash(image):
    digest = hashlib.sha256(image)
    remaining = SIZE - len(image)
    zeros = bytes(CHUNK)
    while remaining:
        count = min(CHUNK, remaining)
        digest.update(zeros[:count])
        remaining -= count
    return digest.hexdigest()


def validate_manifest(expected, actual):
    require(expected.get("format") == actual["format"], "Unsupported preflight manifest")
    for key in ("image_sha256", "image_size_bytes", "padded_image_sha256",
                "parent_disk", "parent_original_read_only", "targets", "backup_policy"):
        require(expected.get(key) == actual[key], f"Preflight changed: {key}")
    for key in ("serial", "root_partuuid", "root_id", "root_source", "root_fstype", "root_rw", "root_ext4_errors"):
        require(expected.get("health", {}).get(key) == actual["health"][key],
                f"Preflight device/root identity changed: {key}")


def write_payload(node, image):
    with node.open("r+b", buffering=0) as stream:
        data = memoryview(image)
        while data:
            count = stream.write(data)
            require(count is not None and count > 0, f"Short write: {node}")
            data = data[count:]
        # Avoid allocating a second 64 MiB payload solely for zero padding.
        zeros = memoryview(bytes(CHUNK))
        remaining = SIZE - len(image)
        while remaining:
            count = stream.write(zeros[:min(CHUNK, remaining)])
            require(count is not None and count > 0, f"Short padding write: {node}")
            remaining -= count
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--device-config", required=True, type=Path,
                        help="explicit private JSON identity/geometry for this existing installation")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    plan = load_device_config(args.device_config)
    require(os.geteuid() == 0, "Run as root for boot partition access")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", args.image_sha256)), "Invalid image SHA256")
    require(args.apply == (args.preflight is not None), "--apply requires --preflight; preflight is read-only otherwise")
    info = args.image.stat()
    require(stat.S_ISREG(info.st_mode) and 8 <= info.st_size <= SIZE,
            "Candidate must be a regular boot image no larger than its partition")
    image = args.image.read_bytes()
    require(8 <= len(image) <= SIZE and image[:8] == b"ANDROID!", "Invalid Android-format boot image")
    require(hashlib.sha256(image).hexdigest() == args.image_sha256, "Candidate image hash mismatch")
    new_hash = padded_hash(image)
    state = health(plan)
    disk_ro = ro(DISK)
    targets = inspect_targets(new_hash)
    manifest = {"format": "j706f-display-boot-preflight-v1", "health": state,
                "image_sha256": args.image_sha256, "image_size_bytes": len(image),
                "padded_image_sha256": new_hash, "parent_disk": str(DISK),
                "parent_original_read_only": disk_ro, "targets": targets,
                "backup_policy": "none-explicit-user-waiver"}
    if not args.apply:
        print(json.dumps(manifest, indent=2), flush=True)
        return
    validate_manifest(json.loads(args.preflight.read_text()), manifest)
    print(json.dumps({"phase": "preflight-revalidated", "manifest": manifest}), flush=True)
    try:
        health(plan)
        set_ro(DISK, 0)
        for target in targets:
            node = Path(target["device"])
            health(plan)
            require(full_hash(node) == target["old_full_sha256"], "Boot partition changed before write")
            if target["old_full_sha256"] == new_hash:
                print(json.dumps({"phase": "already-installed", "target": target["target"]}), flush=True)
                continue
            try:
                set_ro(node, 0)
                print(json.dumps({"phase": "writing", "target": target["target"]}), flush=True)
                write_payload(node, image)
                observed = full_hash(node)
                require(observed == new_hash, f"Full partition verification failed: {node}")
                print(json.dumps({"phase": "verified", "target": target["target"],
                                  "full_sha256": observed}), flush=True)
            finally:
                set_ro(node, target["original_read_only"])
    finally:
        failures = []
        for node, value in [(DISK, disk_ro)] + [
                (Path(t["device"]), t["original_read_only"]) for t in targets]:
            try:
                set_ro(node, value)
            except Exception as error:
                failures.append(f"{node}: {error}")
        require(not failures, "Failed to restore read-only flags: " + "; ".join(failures))
    print(json.dumps({"phase": "complete", "both_boot_partitions_verified": True,
                      "normal_boot_acceptance": "pending", "reboot_requested": False}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"phase": "failed", "error": str(error)}), file=sys.stderr, flush=True)
        sys.exit(1)
