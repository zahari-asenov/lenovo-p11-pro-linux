#!/bin/sh
set -eu
[ -f /etc/j706f-device.conf ] && [ ! -L /etc/j706f-device.conf ]
[ "$(stat -c %u /etc/j706f-device.conf)" = 0 ]
case "$(stat -c %a /etc/j706f-device.conf)" in 600|644) ;; *) exit 90 ;; esac
. /etc/j706f-device.conf
: "${J706F_SERIAL:?}"
[ "$J706F_SERIAL" != CONFIGURE_DEVICE_SERIAL ]
grep -Fqw "androidboot.serialno=$J706F_SERIAL" /proc/cmdline
node=/dev/disk/by-partuuid/${J706F_STORAGE_PARTUUID:?}
[ "$(readlink -f "$node")" = /dev/sda9 ]
[ "$(blockdev --getsize64 "$node")" = 12884901888 ]
[ "$(blkid -s TYPE -o value "$node")" = ext4 ]
[ "$(blkid -s LABEL -o value "$node")" = Linux-Storage ]
blockdev --setrw "$node"
mkdir -p /srv/storage
mountpoint -q /srv/storage || mount -t ext4 -o defaults "$node" /srv/storage
