#!/bin/sh
# Requires the compiled fastboot-shutdown hook installed on the tablet.
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run with sudo.' >&2
    exit 1
fi
test -x /usr/lib/systemd/system-shutdown/90-j706f-fastboot
umask 077
printf bootloader > /run/j706f-fastboot-once
sync
if ! systemctl --reboot-argument=bootloader reboot; then
    rm -f /run/j706f-fastboot-once
    exit 1
fi
