#!/usr/bin/env python3
"""Replace only init/config in the existing bootstrap; preserve other CPIO entries."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import subprocess
from project_config import build_root, load_config, shell_root_config

ROOT = Path(__file__).resolve().parents[1]
BUILD = build_root()
plan = load_config('persistent', require_device=True)
base = BUILD / 'ramdisk.cpio.gz'
source = gzip.decompress(base.read_bytes())
config = shell_root_config(plan)
replacements = {'init': (ROOT / 'bootstrap/init-persistent').read_bytes(),
                'etc/j706f-root.conf': config}
subprocess.run(['sh', '-n', str(ROOT / 'bootstrap/init-persistent')], check=True)

def entry(name, data, mode=0o100644):
    fields = [0, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name.encode()) + 1, 0]
    header = b'070701' + ''.join(f'{x:08x}' for x in fields).encode()
    out = header + name.encode() + b'\0'
    out += b'\0' * (-len(out) % 4)
    out += data
    return out + b'\0' * (-len(out) % 4)

result = bytearray()
i = 0
seen = set()
while i + 110 <= len(source):
    header = source[i:i+110]
    assert header[:6] == b'070701', 'expected newc CPIO'
    size, namesize = int(header[54:62], 16), int(header[94:102], 16)
    assert namesize > 0
    name = source[i+110:i+110+namesize-1].decode()
    start = (i + 110 + namesize + 3) & ~3
    end = (start + size + 3) & ~3
    assert end <= len(source), 'truncated CPIO'
    if name == 'TRAILER!!!':
        break
    key = name.removeprefix('./')
    assert key not in seen, 'duplicate CPIO entry'
    seen.add(key)
    if key in replacements:
        result.extend(entry(name, replacements.pop(key), 0o100755 if key == 'init' else 0o100644))
    else:
        result.extend(source[i:end])
    i = end
else:
    raise ValueError('missing CPIO trailer')
assert 'init' in seen and 'etc' in seen
for name, data in replacements.items():
    result.extend(entry(name, data))
result.extend(entry('TRAILER!!!', b'', 0))
result.extend(b'\0' * (-len(result) % 512))
output = BUILD / 'persistent'
output.mkdir(mode=0o700, exist_ok=True)
archive = output / 'ramdisk.cpio.gz'
archive.write_bytes(gzip.compress(bytes(result), mtime=0))
(output / 'ramdisk.json').write_text(json.dumps({
    'status': 'OFFLINE_PREPARED_NOT_DEVICE_TESTED',
    'base_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'changed_entries': ['init', 'etc/j706f-root.conf'],
    'target_partuuid': plan['partuuid'],
}, indent=2) + '\n')
print('Prepared persistent ramdisk:', archive)
