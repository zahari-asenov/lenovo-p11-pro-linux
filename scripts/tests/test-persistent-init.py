#!/usr/bin/env python3
"""Exercise root selection and fail-closed behavior with mocked mounts/devices."""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads((ROOT / 'configs/persistent.json').read_text())

class PersistentInit(unittest.TestCase):
    def exercise(self, *, serial=None, uuid=None, size=None, fs='ext4', marker=None, probe=False):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "runner" / "work"
            for name in ['sys', 'devices/sda/sda15', 'devices/sdb/sdb1', 'dev', 'run', 'newroot/etc', 'newroot/sbin']:
                (t / name).mkdir(parents=True, exist_ok=True)
            for name in ['sda', 'sda15', 'sdb', 'sdb1']:
                target = t / ('devices/sda' if name == 'sda' else 'devices/sda/sda15' if name == 'sda15' else 'devices/sdb' if name == 'sdb' else 'devices/sdb/sdb1')
                (t/'sys'/name).symlink_to(target)
                (target/'dev').touch()
                (t/'dev'/name).touch()
                if name in ('sda15', 'sdb1'):
                    (target/'partition').write_text('15' if name == 'sda15' else '1')
                    (target/'uevent').write_text(f'PARTUUID={uuid or PLAN["partuuid"] if name == "sda15" else "other"}\nPARTNAME=userdata\n')
                    (target/'size').write_text(str(size or PLAN['sectors_512']))
            (t/'newroot/etc/j706f-root-id').write_text(marker or PLAN['root_id'])
            (t/'newroot/sbin/init').touch(mode=0o755)
            (t/'cmdline').write_text('androidboot.serialno=' + (serial or PLAN['serial']) + (' j706f_root_probe=1' if probe else ''))
            (t/'root.conf').write_text(f'J706F_SERIAL={PLAN["serial"]}\nJ706F_PARTUUID={PLAN["partuuid"]}\nJ706F_SECTORS={PLAN["sectors_512"]}\nJ706F_ROOT_ID={PLAN["root_id"]}\n')
            bb = t/'busybox'
            bb.write_text('#!/bin/sh\ncase "$1" in\n'
                          'blockdev) echo "$*" >>"$TEST_EVENTS";;\n'
                          f'blkid) echo \'TYPE="{fs}"\';;\n'
                          'switch_root) echo SWITCH_ROOT >>"$TEST_EVENTS";;\n'
                          '*) exec "$@";;\nesac\n')
            bb.chmod(0o755)
            script = (ROOT/'bootstrap/init-persistent').read_text().split('B=/bin/busybox-ui\n', 1)[1]
            # Mock block-node type checks, kernel sysfs and mount operations;
            # all selection/identity logic remains the production shell code.
            # Substitute once: chained replacements corrupt inserted paths when
            # the host temporary directory contains a component like /runner.
            paths = {'/sys/class/block': str(t/'sys'), '/dev/': str(t/'dev')+'/',
                     '/etc/j706f-root.conf': str(t/'root.conf'),
                     '/proc/cmdline': str(t/'cmdline'), '/newroot': str(t/'newroot'),
                     '/run': str(t/'run'), '/bin/busybox-ui': str(bb)}
            script = re.sub('|'.join(re.escape(p) for p in sorted(paths, key=len, reverse=True)),
                            lambda match: paths[match.group()], script)
            script = script.replace('[ -b ', '[ -e ')
            prelude = f'''B={bb}
say() {{ echo "$*"; }}
dmesg() {{ :; }}
sleep() {{ [ "$1" != 60 ] || exit 77; }}
mount() {{ echo "mount $*" >>"$TEST_EVENTS"; }}
umount() {{ echo "umount $*" >>"$TEST_EVENTS"; }}
'''
            env = dict(os.environ, TEST_EVENTS=str(t/'events'))
            r = subprocess.run(['sh'], input=prelude+script, text=True, capture_output=True, env=env, timeout=5)
            events = (t/'events').read_text() if (t/'events').exists() else ''
            return r, events

    def test_valid_root(self):
        r, events = self.exercise()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('SWITCH_ROOT', events)
        self.assertIn('mount -t ext4 -o ro,noload', events)
        self.assertIn('mount -t ext4 -o rw', events)
        self.assertIn('blockdev --setro', events)

    def test_reject_invalid_identity(self):
        for args in [dict(serial='WRONG'), dict(uuid='wrong'), dict(size=123), dict(fs='f2fs'), dict(marker='wrong')]:
            with self.subTest(args=args):
                r, events = self.exercise(**args)
                self.assertEqual(r.returncode, 77, r.stderr)
                self.assertNotIn('mount -t ext4 -o rw', events)
                self.assertNotIn('SWITCH_ROOT', events)

    def test_probe_never_mounts_writable(self):
        r, events = self.exercise(probe=True)
        self.assertEqual(r.returncode, 77)
        self.assertIn('read-only root probe passed', r.stdout)
        self.assertNotIn('mount -t ext4 -o rw', events)
        self.assertNotIn('SWITCH_ROOT', events)

if __name__ == '__main__':
    unittest.main()
