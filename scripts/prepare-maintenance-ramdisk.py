#!/usr/bin/env python3
"""Prepare RAM-only assessment, optionally with a guarded explicit repair trigger."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import subprocess
from project_config import build_root, load_config, shell_root_config

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--allow-root-repair', action='store_true',
                    help='include a fixed opt-in HTTP trigger for guarded offline preen')
options = parser.parse_args()
BUILD = build_root()
plan = load_config('persistent', require_device=True)
work = BUILD / 'maintenance'
source = gzip.decompress((BUILD / 'ramdisk.cpio.gz').read_bytes())
tail = (ROOT / 'bootstrap/maintenance-check.sh').read_bytes()
subprocess.run(['sh', '-n', str(ROOT / 'bootstrap/maintenance-check.sh')], check=True)
repair_files = {}
identity_config = shell_root_config(plan)
if options.allow_root_repair:
    repair = (ROOT / 'scripts/repair-root-offline.sh').read_bytes()
    subprocess.run(['sh', '-n', str(ROOT / 'scripts/repair-root-offline.sh')], check=True)
    handler = b'''#!/bin/sh
B=/bin/busybox-ui
reply() {
    body=$2
    printf 'HTTP/1.0 %s\\r\\nContent-Type: text/plain\\r\\nContent-Length: %s\\r\\nConnection: close\\r\\n\\r\\n%s' "$1" "${#body}" "$body"
    exit 0
}
cr=$(printf '\\r')
IFS= read -r request || exit 1
request=${request%"$cr"}
[ "${#request}" -le 128 ] || reply '400 Bad Request' 'Request too large'
case "$request" in
    'GET /ready HTTP/1.0'|'GET /ready HTTP/1.1') method=GET ;;
    'POST /root-preen HTTP/1.0'|'POST /root-preen HTTP/1.1') method=POST ;;
    *) reply '400 Bad Request' 'Rejected request' ;;
esac
count=0
length=
while IFS= read -r line; do
    line=${line%"$cr"}
    [ -n "$line" ] || break
    count=$((count + 1))
    [ "$count" -le 32 ] && [ "${#line}" -le 1024 ] || reply '400 Bad Request' 'Headers too large'
    key=${line%%:*}
    value=${line#*:}
    key=$(printf '%s' "$key" | $B tr 'A-Z' 'a-z')
    case "$key" in
        content-length)
            [ -z "$length" ] || reply '400 Bad Request' 'Duplicate length'
            case "$value" in ' 24'|'24') length=24 ;; *) reply '400 Bad Request' 'Invalid length' ;; esac ;;
        transfer-encoding) reply '400 Bad Request' 'Transfer encoding rejected' ;;
    esac
done
[ -z "$line" ] || reply '400 Bad Request' 'Incomplete headers'
if [ "$method" = GET ]; then
    [ -z "$length" ] || reply '400 Bad Request' 'Unexpected body'
    reply '200 OK' 'Ready: guarded preen requires explicit POST'
fi
[ "$length" = 24 ] || reply '400 Bad Request' 'Length required'
token=$($B dd bs=1 count=24 2>/dev/null)
[ "$token" = 'action=repair-root-preen' ] || reply '403 Forbidden' 'Invalid token'
[ "$(cat /run/www/metadata-ready.txt 2>/dev/null)" = ready ] || reply '409 Conflict' 'Metadata capture not ready'
$B mkdir /run/root-repair-started 2>/dev/null || reply '409 Conflict' 'Repair already requested'
(
    /sbin/j706f-repair-root-offline --apply
    printf '%s\\n' "$?" >/run/www/repair-control-exit.txt
) </dev/null >/run/www/repair-control-run.txt 2>&1 &
reply '202 Accepted' 'Guarded preen requested; inspect HTTP port 80 results'
'''
    subprocess.run(['sh', '-n'], input=handler, check=True)
    repair_files = {'sbin/j706f-repair-root-offline': repair,
                    'sbin/j706f-root-repair-http': handler}
    marker = b'# J706F_ROOT_REPAIR_HTTP'
    assert tail.count(marker) == 1, 'Missing unique repair HTTP integration marker'
    startup = b'''# Explicit POST only; no repair runs on startup or GET.
(
    while :; do
        /bin/busybox-ui nc -l -p 82 -e /sbin/j706f-root-repair-http || sleep 1
    done
) </dev/null >/run/www/repair-control.log 2>&1 &'''
    tail = tail.replace(marker, startup)
tools = {'sbin/e2fsck': 'e2fsck', 'lib/ld-linux-aarch64.so.1': 'ld-linux-aarch64.so.1'}
for name in ['libext2fs.so.2', 'libcom_err.so.2', 'libblkid.so.1',
             'libuuid.so.1', 'libe2p.so.2', 'libc.so.6']:
    tools['lib/aarch64-linux-gnu/' + name] = name


def entry(name, data, mode=0o100644):
    fields = [0, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name.encode()) + 1, 0]
    out = b'070701' + ''.join(f'{v:08x}' for v in fields).encode() + name.encode() + b'\0'
    out += b'\0' * (-len(out) % 4)
    out += data
    return out + b'\0' * (-len(out) % 4)


result = bytearray()
i = 0
seen = set()
while i + 110 <= len(source):
    header = source[i:i+110]
    assert header[:6] == b'070701'
    size, namesize = int(header[54:62], 16), int(header[94:102], 16)
    name = source[i+110:i+110+namesize-1].decode()
    start = (i + 110 + namesize + 3) & ~3
    end = (start + size + 3) & ~3
    assert end <= len(source)
    if name == 'TRAILER!!!':
        break
    key = name.removeprefix('./')
    assert key not in seen
    seen.add(key)
    if key == 'etc/j706f-root.conf':
        # Always replace an old identity; never inherit a different target.
        pass
    elif key == 'init':
        base_init = source[start:start+size]
        prefix, marker, _ = base_init.partition(b'B=/bin/busybox-ui\n')
        assert marker and b'httpd -p 80' in prefix
        result.extend(entry(name, prefix + tail, 0o100755))
    else:
        assert key not in tools and key not in repair_files
        result.extend(source[i:end])
    i = end
else:
    raise ValueError('Missing CPIO trailer')
assert 'init' in seen and 'etc' in seen, 'Base initramfs must contain init and etc'
result.extend(entry('etc/j706f-root.conf', identity_config))
result.extend(entry('lib/aarch64-linux-gnu', b'', 0o40755))
hashes = {}
code_hashes = {'bootstrap/maintenance-check.sh': hashlib.sha256(tail).hexdigest(),
               'etc/j706f-root.conf': hashlib.sha256(identity_config).hexdigest()}
for name, data in repair_files.items():
    result.extend(entry(name, data, 0o100755))
    code_hashes[name] = hashlib.sha256(data).hexdigest()
for name, filename in tools.items():
    data = (work / 'tools' / filename).read_bytes()
    assert data[:4] == b'\x7fELF'
    result.extend(entry(name, data, 0o100755))
    hashes[name] = hashlib.sha256(data).hexdigest()
result.extend(entry('TRAILER!!!', b'', 0))
result.extend(b'\0' * (-len(result) % 512))
archive = work / 'ramdisk.cpio.gz'
archive.write_bytes(gzip.compress(bytes(result), mtime=0))
(work / 'ramdisk.json').write_text(json.dumps({
    'status': 'OFFLINE_PREPARED_NOT_DEVICE_TESTED',
    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'base_sha256': hashlib.sha256((BUILD / 'ramdisk.cpio.gz').read_bytes()).hexdigest(),
    'tools_sha256': hashes,
    'target': '/dev/sda15', 'filesystem_writes': options.allow_root_repair,
    'code_sha256': code_hashes,
    'repair_policy': 'explicit-fixed-POST-offline-preen-no-auto-run' if options.allow_root_repair else 'read-only',
}, indent=2) + '\n')
print('Maintenance initramfs prepared; no device commands issued')
