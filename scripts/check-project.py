#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run offline project checks without a tablet, firmware, archive or root image.

Requires Python 3 with PyYAML, PyGObject/Gio and desktop schemas, a host C compiler,
device-tree-compiler, POSIX sh and bash. Generated files stay outside checkout.
These checks do not prove a kernel build, successful device boot or hardware fix.
"""

import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, env):
    print("+ " + shlex.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True)


def check_sources(env):
    python_count = shell_count = 0
    for folder in ("scripts", "bootstrap", "configs"):
        for path in sorted((ROOT / folder).rglob("*")):
            if (not path.is_file() or "__pycache__" in path.parts or
                    path.is_relative_to(ROOT / "configs/local")):
                continue
            if path.suffix == ".py":
                # Compile syntax in memory: do not execute tools or write .pyc.
                compile(path.read_bytes(), str(path), "exec")
                python_count += 1
            elif path.suffix == ".sh" or path.read_bytes()[:2] == b"#!":
                first = path.read_bytes().splitlines()[0]
                if b"bash" in first:
                    run(["bash", "-n", path], env)
                    shell_count += 1
                elif path.suffix == ".sh" or re.search(rb"(?:^|[/\s])sh(?:\s|$)", first):
                    run(["sh", "-n", path], env)
                    shell_count += 1
    print(f"PASS: Python syntax ({python_count}) and shell syntax ({shell_count})", flush=True)


def check_configs():
    configs = {}
    for path in sorted((ROOT / "configs").rglob("*.json")):
        if path.is_relative_to(ROOT / "configs/local"):
            continue
        configs[path.relative_to(ROOT / "configs").as_posix()] = json.loads(path.read_text())
    plan = configs["persistent.json"]
    uuid.UUID(plan["partuuid"])
    require(plan["bytes"] == plan["sectors_512"] * 512, "Root plan geometry disagrees")
    require(plan["boot_bytes"] == 64 * 1024 * 1024, "Unexpected boot partition geometry")
    if plan["serial"] == "CONFIGURE_DEVICE_SERIAL":
        require(plan["partuuid"] == str(uuid.UUID(int=0)) and
                plan["root_id"] == "CONFIGURE_EXISTING_ROOT_MARKER",
                "Public device template must remain unconfigured")
    else:
        require(plan["root_id"].endswith(f':{plan["serial"]}:{plan["partuuid"]}'),
                "Root identity marker disagrees with root plan")
    for name in ("boot.json", "boot-persistent.json"):
        config = configs[name]
        require(config["serial"] == plan["serial"], f"Serial disagreement in {name}")
        require(isinstance(config["root_archive"], str) and config["root_archive"],
                f"Missing root input declaration in {name}")
        require(config["cmdline"].split().count("rdinit=/init") == 1,
                f"Unexpected init command line in {name}")
        require(len(config["cmdline"].encode()) <= 1536, f"Boot command line exceeds v2 header: {name}")
    require(f'root=PARTUUID={plan["partuuid"]}' in configs["boot-persistent.json"]["cmdline"].split(),
            "Persistent boot command line disagrees with root plan")
    board_config = (ROOT / "configs/j706f.config").read_text().splitlines()
    for key in ("ARM64", "ARCH_QCOM", "DRM_MSM", "DRM_MSM_DSI", "DRM_PANEL_LENOVO_J706F"):
        require(f"CONFIG_{key}=y" in board_config, f"Board config missing CONFIG_{key}=y")
    print(f"PASS: {len(configs)} JSON files and board/root/boot configuration consistency", flush=True)


def check_workflow_configuration():
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError("Install python3-yaml to validate workflow and issue-template YAML") from error
    count = 0
    for path in sorted((ROOT / ".github").rglob("*.yml")):
        # BaseLoader keeps GitHub's 'on' key literal instead of YAML 1.1 boolean.
        data = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        require(isinstance(data, dict), f"YAML mapping required: {path}")
        if path.parent.name == "workflows":
            require(data.get("permissions") == {"contents": "read"},
                    f"Workflow token must be read-only: {path}")
            require(isinstance(data.get("on"), dict) and data.get("jobs"),
                    f"Workflow events/jobs missing: {path}")
            for job in data["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" in step:
                        require(bool(re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])),
                                f"Action must use a full commit pin: {step['uses']}")
        count += 1
    print(f"PASS: {count} workflow/template YAML files; workflow tokens and action pins", flush=True)


def check_package_roundtrip(work, env):
    inputs = {
        "kernel": gzip.compress(b"synthetic test bytes; not a runnable kernel\n", mtime=0),
        "ramdisk": gzip.compress(b"synthetic archive bytes; not a runnable initramfs\n", mtime=0),
        "dtb": b"\xd0\x0d\xfe\xed" + b"synthetic roundtrip bytes; not a valid device tree\n",
    }
    command = [sys.executable, ROOT / "scripts/mkbootimg.py"]
    for name, payload in inputs.items():
        path = work / name
        path.write_bytes(payload)
        command.extend([f"--{name}", path])
    image = work / "synthetic.img"
    command.extend(["--header_version", "2", "--pagesize", "4096", "--base", "0",
                    "--kernel_offset", "0x8000", "--ramdisk_offset", "0x01000000",
                    "--tags_offset", "0x100", "--dtb_offset", "0x01f00000",
                    "--os_version", "11.0.0", "--os_patch_level", "2023-08",
                    "--cmdline", "rdinit=/init synthetic-check-only=1", "--output", image])
    run(command, env)
    output = work / "unpacked"
    run([sys.executable, ROOT / "scripts/unpack_bootimg.py", "--boot_img", image,
         "--out", output], env)
    for name, payload in inputs.items():
        require((output / name).read_bytes() == payload, f"Boot payload roundtrip failed: {name}")
    require(image.stat().st_size < 64 * 1024 * 1024, "Synthetic boot image too large")
    print("PASS: synthetic Android v2 boot header/payload roundtrip (not a device image)", flush=True)


def check_installer_helpers(work):
    spec = importlib.util.spec_from_file_location("display_installer", ROOT / "scripts/install-display-boot.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    # Exercise the same stream writer/hash code using regular host files only.
    installer.SIZE, installer.CHUNK = 4096, 1024
    node = work / "fake-boot-partition"
    for size in (8, 1024, 2049, 4096):
        payload = b"ANDROID!" + bytes(i % 251 for i in range(size - 8))
        node.write_bytes(b"X" * installer.SIZE)
        installer.write_payload(node, payload)
        require(node.read_bytes() == payload + bytes(installer.SIZE - size),
                f"Installer padding mismatch at size {size}")
        require(installer.full_hash(node) == installer.padded_hash(payload), "Installer readback mismatch")
    print("PASS: boot installer stream/padding/readback boundary checks using host files", flush=True)


def main():
    require(sys.version_info >= (3, 11), "Use Python 3.11 or newer")
    for command in ("bash", "sh", "cc", "dtc", "fdtget", "fdtput"):
        require(shutil.which(command), f"Missing host check dependency: {command}")
    try:
        from gi.repository import Gio  # noqa: F401
    except ImportError as error:
        raise RuntimeError("Use /usr/bin/python3 with python3-gi and gsettings-desktop-schemas installed") from error
    build = Path(os.environ.get("J706F_BUILD_ROOT", str(ROOT.parent / "j706f-build"))).resolve()
    require(not build.is_relative_to(ROOT), "J706F_BUILD_ROOT must be outside the checkout")
    checks = build / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="host-", dir=checks) as temporary:
        work = Path(temporary)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(work),
                   GSETTINGS_BACKEND="memory", PYTHONPYCACHEPREFIX=str(work / "pycache"))
        # Also suppress cache files from the safe installer import in this process.
        sys.dont_write_bytecode = True
        check_sources(env)
        check_configs()
        check_workflow_configuration()
        run([sys.executable, ROOT / "scripts/tests/test-persistent-init.py"], env)
        run([sys.executable, ROOT / "scripts/tests/test_screen_contrast.py"], env)
        run([sys.executable, ROOT / "scripts/tests/test_project_config.py"], env)
        run([sys.executable, ROOT / "scripts/tests/test_local_dtb.py"], env)
        policy = work / "test-charge-policy"
        run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             ROOT / "scripts/tests/test-j706f-charge-policy.c", "-o", policy], env)
        run([policy], env)
        brightness = work / "test-brightness"
        run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             ROOT / "scripts/tests/test-j706f-brightness.c", "-o", brightness], env)
        run([brightness], env)
        check_package_roundtrip(work, env)
        check_installer_helpers(work)
    print("PASS: all offline host checks; kernel build and device acceptance are separate", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Host checks failed: {error}", file=sys.stderr)
        sys.exit(1)
