#!/bin/sh
# Run the packaged Qualcomm boot-control HAL, preserving disk RO policy.
set -eu
[ "$(id -u)" = 0 ]
[ -f /etc/j706f-device.conf ] && [ ! -L /etc/j706f-device.conf ]
[ "$(stat -c %u /etc/j706f-device.conf)" = 0 ]
case "$(stat -c %a /etc/j706f-device.conf)" in 600|644) ;; *) exit 90 ;; esac
. /etc/j706f-device.conf
: "${J706F_SERIAL:?}"
[ "$J706F_SERIAL" != CONFIGURE_DEVICE_SERIAL ]
grep -Fqw "androidboot.serialno=$J706F_SERIAL" /proc/cmdline
[ "$(findmnt -n -o SOURCE /)" = /dev/sda15 ]
[ "$(cat /etc/j706f-root-id)" = "${J706F_ROOT_ID:?}" ]
# All firmware partitions stay RO; only whole-disk GPT access is opened briefly.
restore=
cleanup() {
 for disk in $restore; do blockdev --setro "$disk"; done
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
for name in sda sdb sdc sde; do
 disk=/dev/$name
 if [ "$(blockdev --getro "$disk")" = 1 ]; then
  restore="$restore $disk"
  blockdev --setrw "$disk"
 fi
 for part in /sys/class/block/$name/*; do
  [ -f "$part/partition" ] || continue
  [ "${part##*/}" = sda15 ] && continue
  # The reclaimed Android system partition is Linux data storage.
  if [ "${part##*/}" = sda9 ] && grep -Fqx "PARTUUID=${J706F_STORAGE_PARTUUID:?}" "$part/uevent"; then
   continue
  fi
  blockdev --setro /dev/"${part##*/}"
 done
done
/usr/bin/qbootctl -m
/usr/bin/qbootctl
