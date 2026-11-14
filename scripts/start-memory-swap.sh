#!/bin/sh
# Configure compressed swap without touching the root filesystem.
set -eu
test "$(id -u)" = 0
test -d /sys/block/zram0
if swapon --noheadings --raw --show=NAME | grep -qx /dev/zram0; then
    exit 0
fi
# Refuse to overwrite a device configured by another service.
test "$(cat /sys/block/zram0/disksize)" = 0
echo lz4 > /sys/block/zram0/comp_algorithm
echo 3221225472 > /sys/block/zram0/disksize
mkswap /dev/zram0
swapon --priority 100 /dev/zram0
