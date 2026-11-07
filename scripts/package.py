#!/usr/bin/env python3
"""Replace the current test image only after a header/payload round trip."""
from pathlib import Path
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import tempfile
from project_config import build_root, load_config

ROOT = Path(__file__).resolve().parents[1]
BUILD = build_root()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--persistent', action='store_true', help='package the offline persistent-root candidate')
parser.add_argument('--maintenance', action='store_true', help='package the RAM-only filesystem assessment initramfs')
parser.add_argument('--allow-root-repair', action='store_true', help='explicitly package an opted-in guarded maintenance repair initramfs')
parser.add_argument('--reuse-prepared-root', action='store_true',
                    help='reuse a hash-verified persistent root prepared at an earlier source revision')
parser.add_argument('--j706f-command-master0', action='store_true',
                    help='opt into the J706F command-controller experiment (persistent RAM test)')
options = parser.parse_args()
if options.maintenance and options.persistent:
    parser.error('--maintenance and --persistent are mutually exclusive')
if options.reuse_prepared_root and not options.persistent:
    parser.error('--reuse-prepared-root requires --persistent')
if options.allow_root_repair and not options.maintenance:
    parser.error('--allow-root-repair requires --maintenance')
if options.j706f_command_master0 and not options.persistent:
    parser.error('--j706f-command-master0 requires --persistent')
config = load_config('boot-persistent' if options.persistent else 'boot', require_device=True)
plan = load_config('persistent', require_device=True) if options.persistent or options.maintenance else None
if plan is not None:
    assert config['serial'] == plan['serial'], 'Boot and root device identities disagree'
if options.persistent:
    assert f"root=PARTUUID={plan['partuuid']}" in config['cmdline'].split(), 'Boot/root partition UUIDs disagree'
if options.j706f_command_master0:
    # Lenovo ABL drops the extended command-line field. Keep the experiment
    # and root identity in the legacy 512-byte field; omit verbose logging.
    verbose = {'ignore_loglevel', 'keep_bootcon', 'initcall_debug',
               'systemd.show_status=yes'}
    config['cmdline'] = 'msm.j706f_cmd_master0=1 ' + ' '.join(
        word for word in config['cmdline'].split() if word not in verbose)
    assert len(config['cmdline'].encode()) < 512, 'Test command line exceeds ABL limit'
if options.maintenance:
    config['cmdline'] = config['cmdline'].replace('j706f_diag=dma-watermarks', 'j706f_diag=filesystem-check').replace('root=/dev/loop0 rw ', '')
    config['root_archive'] = None
parts = {
    'kernel': BUILD / 'kernel/arch/arm64/boot/Image.gz',
    'ramdisk': BUILD / ('persistent/ramdisk.cpio.gz' if options.persistent else 'ramdisk.cpio.gz'),
    'dtb': BUILD / 'kernel/arch/arm64/boot/dts/qcom/sm7150-lenovo-j706f-power.dtb',
}
if options.maintenance:
    parts['ramdisk'] = BUILD / 'maintenance/ramdisk.cpio.gz'
for path in parts.values():
    assert path.is_file(), f'Missing build input: {path}'
root_archive = None if options.maintenance else BUILD / ('persistent/rootfs.ext4' if options.persistent else 'artifacts/' + config['root_archive'])
if root_archive is not None:
    assert root_archive.is_file()

def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
with tempfile.TemporaryDirectory(prefix='package-', dir=BUILD) as tmp:
    tmp = Path(tmp)
    image = tmp / 'current-test.img'
    args = [sys.executable, str(ROOT / 'scripts/mkbootimg.py')]
    for role, path in parts.items():
        args.extend(['--' + role, str(path)])
    args.extend(['--header_version', '2', '--pagesize', '4096', '--base', '0',
                 '--kernel_offset', '0x8000', '--ramdisk_offset', '0x01000000',
                 '--tags_offset', '0x100', '--dtb_offset', '0x01f00000',
                 '--os_version', '11.0.0', '--os_patch_level', '2023-08',
                 '--cmdline', config['cmdline'], '--output', str(image)])
    subprocess.run(args, check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/unpack_bootimg.py'),
                    '--boot_img', str(image), '--out', str(tmp / 'roundtrip')],
                   check=True, stdout=subprocess.DEVNULL)
    for role, path in parts.items():
        assert (tmp / 'roundtrip' / role).read_bytes() == path.read_bytes(), role
    assert image.stat().st_size < 0x4000000
    digest = sha256(image)
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True))
    manifest = {'status': 'OFFLINE_VALIDATED_NOT_DEVICE_TESTED', 'source_commit': revision,
                'source_dirty': dirty, 'sha256': digest, 'cmdline': config['cmdline'],
                'root_archive': config['root_archive'], 'root_archive_sha256': sha256(root_archive) if root_archive else None,
                'payload_sha256': {role: sha256(path) for role, path in parts.items()},
                'kernel_config_sha256': sha256(BUILD / 'kernel/.config'),
                'packaged_at_utc': datetime.now(timezone.utc).isoformat(),
                'header_roundtrip': True}
    if options.maintenance:
        manifest['maintenance'] = json.loads((BUILD / 'maintenance/ramdisk.json').read_text())
        assert manifest['maintenance']['sha256'] == manifest['payload_sha256']['ramdisk']
        assert manifest['maintenance']['filesystem_writes'] is options.allow_root_repair, 'Prepared maintenance repair mode must match explicit packaging opt-in'
        if options.allow_root_repair:
            assert manifest['maintenance']['repair_policy'] == 'explicit-fixed-POST-offline-preen-no-auto-run'
            assert {'sbin/j706f-repair-root-offline', 'sbin/j706f-root-repair-http'} <= manifest['maintenance']['code_sha256'].keys()
        manifest['boot_mode'] = 'initramfs-maintenance-guarded-repair' if options.allow_root_repair else 'initramfs-maintenance-readonly'
    if options.persistent:
        root_manifest = json.loads((BUILD / 'persistent/rootfs.json').read_text())
        ramdisk_manifest = json.loads((BUILD / 'persistent/ramdisk.json').read_text())
        assert root_manifest['status'] == 'OFFLINE_PREPARED_NOT_DEVICE_TESTED'
        assert root_manifest['root_sha256'] == manifest['root_archive_sha256']
        assert ramdisk_manifest['sha256'] == manifest['payload_sha256']['ramdisk']
        assert not root_manifest['source_dirty'], 'Root preparation must have clean-source provenance'
        if not options.reuse_prepared_root:
            assert root_manifest['source_commit'] == revision, 'Use --reuse-prepared-root for a kernel-only test'
        target = plan['partuuid']
        assert root_manifest['target_partuuid'] == ramdisk_manifest['target_partuuid'] == target
        manifest['root_preparation_reused'] = options.reuse_prepared_root
        assert not dirty, 'Commit source before packaging the persistent candidate'
        assert root_manifest['overlay_readback'] and root_manifest['e2fsck_read_only'] == 'passed'
        manifest['root_preparation'] = root_manifest
        manifest['boot_mode'] = 'persistent-ext4'
        manifest['root_payload_private'] = True
        manifest['target_partuuid'] = plan['partuuid']
    image.chmod(0o444)
    image.replace(BUILD / 'artifacts/current-test.img')
    (BUILD / 'artifacts/current-test.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Current test packaged: {digest}')
    print('Known-good image was not changed. No tablet commands were issued.')
