#!/usr/bin/python3
"""Firmware charger-mode UI: blank display, power release starts GNOME.

No brightness/current/voltage changes. SSH remains available for recovery.
"""
import ctypes
import ctypes.util
import fcntl
import os
from pathlib import Path
import select
import struct
import subprocess
import time

EVENT = struct.Struct('@llHHi')
EVIOCGRAB = 0x40044590


def blank(value):
    # Stop fbcon from repainting boot messages after the DPMS request.
    tty = os.open('/dev/tty1', os.O_RDWR | os.O_NOCTTY)
    try:
        if value:
            os.write(tty, b'\x1b[2J\x1b[H\x1b[?25l')
        fcntl.ioctl(tty, 0x4b3a, 1 if value else 0)  # KDSETMODE
    finally:
        os.close(tty)
    # fbcon blanking leaves the command-mode panel displaying its last frame.
    # Use the connector DPMS property so DRM disables the actual display pipe.
    class Properties(ctypes.Structure):
        _fields_ = [('count', ctypes.c_uint32),
                    ('ids', ctypes.POINTER(ctypes.c_uint32)),
                    ('values', ctypes.POINTER(ctypes.c_uint64))]

    class Property(ctypes.Structure):
        _fields_ = [('id', ctypes.c_uint32), ('flags', ctypes.c_uint32),
                    ('name', ctypes.c_char * 32)]

    drm = ctypes.CDLL(ctypes.util.find_library('drm'), use_errno=True)
    drm.drmModeObjectGetProperties.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32]
    drm.drmModeObjectGetProperties.restype = ctypes.POINTER(Properties)
    drm.drmModeGetProperty.argtypes = [ctypes.c_int, ctypes.c_uint32]
    drm.drmModeGetProperty.restype = ctypes.POINTER(Property)
    drm.drmModeFreeProperty.argtypes = [ctypes.POINTER(Property)]
    drm.drmModeFreeObjectProperties.argtypes = [ctypes.POINTER(Properties)]
    drm.drmModeConnectorSetProperty.argtypes = [ctypes.c_int, ctypes.c_uint32,
                                               ctypes.c_uint32, ctypes.c_uint64]
    connector = int(Path('/sys/class/drm/card0-DSI-1/connector_id').read_text())
    fd = os.open('/dev/dri/card0', os.O_RDWR | os.O_CLOEXEC)
    props = None
    try:
        props = drm.drmModeObjectGetProperties(fd, connector, 0xc0c0c0c0)
        if not props:
            raise OSError(ctypes.get_errno(), 'DRM connector properties')
        for index in range(props.contents.count):
            prop = drm.drmModeGetProperty(fd, props.contents.ids[index])
            if not prop:
                continue
            try:
                if prop.contents.name == b'DPMS':
                    if drm.drmModeConnectorSetProperty(fd, connector, prop.contents.id,
                                                      3 if value else 0):
                        raise OSError(ctypes.get_errno(), 'DRM DPMS')
                    return
            finally:
                drm.drmModeFreeProperty(prop)
        raise RuntimeError('Display DPMS property unavailable')
    finally:
        if props:
            drm.drmModeFreeObjectProperties(props)
        os.close(fd)


def desktop():
    # Permit a later daemon-reload without restoring charger-mode default.
    Path('/run/j706f-charging-bypass').touch()
    try:
        blank(0)
    finally:
        subprocess.run(['systemctl', 'start', '--no-block', 'graphical.target'], check=True)


def main():
    # Match the PMIC power key by identity, never by a fixed event number.
    deadline = time.monotonic() + 30
    device = None
    while time.monotonic() < deadline:
        for entry in Path('/sys/class/input').glob('event*'):
            if (entry / 'device/name').read_text().strip() == 'pm8941_pwrkey':
                device = '/dev/input/' + entry.name
                break
        if device:
            break
        time.sleep(0.5)
    if not device:
        raise RuntimeError('PMIC power key unavailable')
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
        blank(4)
        print('Charging mode active; release Power after pressing to start desktop', flush=True)
        pressed = False
        unplugged = None
        while True:
            # Debounce removal; power off rather than leave Linux running unplugged.
            online = Path('/sys/class/power_supply/pm8150b-charger/online').read_text().strip()
            if online == '0':
                unplugged = unplugged or time.monotonic()
                if time.monotonic() - unplugged >= 5:
                    subprocess.run(['systemctl', 'poweroff', '--no-block'], check=True)
                    return
            else:
                unplugged = None
            if not select.select([fd], [], [], 0.5)[0]:
                continue
            data = os.read(fd, EVENT.size * 32)
            for _, _, kind, code, value in EVENT.iter_unpack(data):
                if kind == 1 and code == 116:
                    if value == 1:
                        pressed = True
                    elif value == 0 and pressed:
                        desktop()
                        return
    finally:
        fcntl.ioctl(fd, EVIOCGRAB, 0)
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # A missing input/display/supply must not strand the user in charger mode.
        desktop()
        raise
