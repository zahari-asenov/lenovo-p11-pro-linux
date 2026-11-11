#!/usr/bin/env python3
"""Archive guarded RAM-maintenance evidence; repair only with explicit --apply."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import struct
import sys
import time
from urllib.parse import urlsplit
from project_config import load_device_config

READY = b'Ready: guarded preen requires explicit POST'
PAIRS = ((33, 'block'), (33, 'inode'), (419, 'block'),
         (460, 'block'), (463, 'block'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def geometry(prefix, expected_bytes):
    """Decode only the reviewed primary-GDT layout, never trust damaged CRCs."""
    require(len(prefix) == 65536, 'Metadata prefix must be exactly 64KiB')
    u16 = lambda offset: struct.unpack_from('<H', prefix, offset)[0]
    u32 = lambda offset: struct.unpack_from('<I', prefix, offset)[0]
    require(u16(1080) == 0xef53, 'Not ext4')
    require(u32(1048) == 2 and u16(1278) == 64, 'Unexpected block/descriptor size')
    require(not u32(1120) & 0x10 and u32(1120) & 0x80,
            'Expected 64-bit descriptors without META_BG')
    blocks = u32(1028) | u32(1360) << 32
    require(blocks * 4096 == expected_bytes, 'Unexpected filesystem size')
    require(u32(1044) == 0 and u32(1056) == 32768 and
            u32(1060) == 32768 and u32(1064) == 8192,
            'Unexpected filesystem group geometry')
    locations = {}
    for group, kind in PAIRS:
        offset = 4096 + group * 64 + (4 if kind == 'inode' else 0)
        require(offset + 36 <= len(prefix), 'Descriptor outside captured GDT')
        block = u32(offset) | u32(offset + 32) << 32
        require(0 < block < blocks, 'Bitmap location outside filesystem')
        locations[f'root-group{group}-{kind}-bitmap.bin'] = block
    return locations


class Client:
    def __init__(self, base, output, device_config):
        url = urlsplit(base)
        require(url.scheme == 'http' and url.hostname and not url.username and
                not url.password and url.path in ('', '/') and
                not url.query and not url.fragment, 'Expected plain HTTP origin without credentials')
        self.host = url.hostname
        self.port = url.port or 80
        self.output = output
        self.device_config = device_config
        self.events = []
        self.manifest = {'files': {}, 'events': self.events, 'state': 'collecting'}

    def save(self, name, data):
        # A fresh output directory and exclusive creation prevent evidence overwrite.
        with (self.output / name).open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.manifest['files'][name] = {'bytes': len(data),
                                       'sha256': hashlib.sha256(data).hexdigest()}

    def checkpoint(self):
        data = json.dumps(self.manifest, indent=2).encode() + b'\n'
        temporary = self.output / '.manifest.tmp'
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.output / 'manifest.json')
        fd = os.open(self.output, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def request(self, name, *, control=False, body=None, missing=False):
        conn = http.client.HTTPConnection(self.host, 82 if control else self.port, timeout=10)
        try:
            conn.request('POST' if body is not None else 'GET', '/' + name, body=body,
                         headers={'Content-Type': 'application/x-www-form-urlencoded'} if body else {})
            response = conn.getresponse()
            data = response.read(4 * 1024 * 1024 + 1)
            self.events.append({'endpoint': name, 'method': 'POST' if body else 'GET',
                                'port': 82 if control else self.port, 'status': response.status})
            require(len(data) <= 4 * 1024 * 1024, 'Response too large')
            if missing and response.status == 404:
                return None
            require(response.status == (202 if body else 200),
                    f'{name}: unexpected HTTP status {response.status}; stop without retrying POST')
            return data
        finally:
            conn.close()

    def fetch(self, name):
        data = self.request(name)
        self.save(name, data)
        return data

    def collect(self):
        tokens = self.fetch('cmdline.txt').decode().split()
        require([x for x in tokens if x.startswith('androidboot.serialno=')] ==
                [f"androidboot.serialno={self.device_config['serial']}"], 'Wrong or ambiguous device serial')
        require([x for x in tokens if x.startswith('j706f_diag=')] ==
                ['j706f_diag=filesystem-check'], 'Not filesystem maintenance RAM boot')
        mounts = self.fetch('maintenance-mounts.txt').decode().splitlines()
        require(bool(mounts), 'Missing mount evidence')
        for line in mounts:
            fields = line.split()
            require(len(fields) >= 6, 'Malformed mount evidence')
            require(not fields[0].startswith('/dev/sd'), 'Internal disk mounted')
            require(not fields[0].startswith(('/dev/disk/', '/dev/root')),
                    'Ambiguous internal mount alias')
        swaps = self.fetch('maintenance-swaps.txt').decode().splitlines()
        require(len(swaps) == 1 and swaps[0].split() ==
                ['Filename', 'Type', 'Size', 'Used', 'Priority'], 'Swap active or malformed evidence')
        require(self.fetch('fsck-exit.txt').strip() in (b'0', b'4'), 'Assessment did not finish with rc0/4')
        self.fetch('fsck-readonly.txt')
        require(self.request('ready', control=True) == READY, 'Unexpected repair handler')
        require(self.fetch('metadata-ready.txt') == b'ready\n', 'Metadata incomplete')
        require(self.fetch('root-metadata-exit.txt') == b'0\n', 'Metadata capture failed')
        locations = geometry(self.fetch('root-metadata-prefix.bin'), self.device_config['bytes'])
        listing = self.fetch('root-metadata-locations.txt').decode().splitlines()
        expected = [f'{group} {kind} {locations[f"root-group{group}-{kind}-bitmap.bin"]}'
                    for group, kind in PAIRS]
        require(listing == expected, 'Capture locations disagree with GDT')
        for filename in locations:
            require(len(self.fetch(filename)) == 4096, 'Bitmap must be exactly one block')
        sums = self.fetch('root-metadata-sha256.txt').decode().splitlines()
        expected_files = {'root-metadata-prefix.bin', 'root-metadata-locations.txt', *locations}
        seen = set()
        for line in sums:
            digest, filename = line.split()
            require(filename in expected_files and filename not in seen, 'Unexpected checksum manifest entry')
            require(self.manifest['files'][filename]['sha256'] == digest, 'Transport/capture SHA256 mismatch')
            seen.add(filename)
        require(seen == expected_files, 'Incomplete checksum manifest')
        self.fetch('root-metadata-capture.txt')
        self.manifest['bitmap_blocks'] = locations
        # Existing completion is evidence, never authorization to repeat repair.
        done = self.request('fsck-repair-done.txt', missing=True)
        if done is not None:
            self.save('preexisting-fsck-repair-done.txt', done)
            raise ValueError('Repair already completed; refusing reapplication')
        self.manifest['state'] = 'validated-read-only'
        self.checkpoint()

    def apply(self):
        # Persist evidence and intent before the sole mutating request. Never retry it.
        self.manifest['state'] = 'explicit-apply-requested'
        self.checkpoint()
        self.save('repair-request-response.txt', self.request(
            'root-preen', control=True, body=b'action=repair-root-preen'))
        deadline = time.monotonic() + 120
        while True:
            done = self.request('fsck-repair-done.txt', missing=True)
            if done is not None:
                self.save('fsck-repair-done.txt', done)
                require(done == b'done\n', 'Unexpected completion marker')
                break
            require(time.monotonic() < deadline, 'Repair result timeout; leave device in RAM')
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        repair = self.fetch('fsck-repair-exit.txt').strip()
        after = self.fetch('fsck-after-repair-exit.txt').strip()
        for name in ('fsck-repair.txt', 'fsck-after-repair.txt', 'repair-control-run.txt'):
            self.fetch(name)
        require(repair in (b'0', b'1', b'2') and after == b'0',
                'Repair or independent check failed; leave device in RAM')
        self.manifest['state'] = 'repair-and-independent-check-passed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='explicit USB maintenance HTTP origin')
    parser.add_argument('--device-config', type=Path, required=True,
                        help='explicit private JSON identity/geometry for this existing installation')
    parser.add_argument('--output', type=Path, required=True, help='new external private evidence directory')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = load_device_config(args.device_config)
    output = args.output.absolute()
    checkout = Path(__file__).resolve().parents[1]
    require(not output.resolve().is_relative_to(checkout), 'Output must be outside checkout')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(output, 0o700)
    client = Client(args.base_url, output, plan)
    try:
        client.collect()
        if args.apply:
            client.apply()
        client.checkpoint()
        print(client.manifest['state'] + '; device remains in RAM')
        return 0
    except Exception as exc:
        client.manifest['state'] = 'stopped'
        client.manifest['error'] = str(exc)
        client.checkpoint()
        print(f'STOP: {exc}; do not reboot; device remains in RAM', file=sys.stderr)
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'STOP: {error}; no reboot requested', file=sys.stderr)
        sys.exit(1)
