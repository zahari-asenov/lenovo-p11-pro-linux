#!/bin/sh
# Only for the reviewed J706F initramfs maintenance environment.
set -eu
B=/bin/busybox-ui
mode=${1:---check}
case "$mode" in --check|--apply) ;; *) exit 2 ;; esac
[ -f /etc/j706f-root.conf ]
. /etc/j706f-root.conf
: "${J706F_SERIAL:?}" "${J706F_PARTUUID:?}" "${J706F_BYTES:?}"
[ "$J706F_SERIAL" != CONFIGURE_DEVICE_SERIAL ]
grep -Fqw "androidboot.serialno=$J706F_SERIAL" /proc/cmdline
grep -qw j706f_diag=filesystem-check /proc/cmdline
grep -Fqx "PARTUUID=$J706F_PARTUUID" /sys/class/block/sda15/uevent
grep -qx PARTNAME=userdata /sys/class/block/sda15/uevent
[ "$($B blockdev --getsize64 /dev/sda15)" = "$J706F_BYTES" ]
for node in /sys/class/block/sd*; do
    [ -e "$node/dev" ] || continue
    dev=$(cat "$node/dev")
    while read -r id parent mounted_dev rest; do
        [ "$mounted_dev" != "$dev" ] || exit 90
    done </proc/self/mountinfo
done
[ "$($B wc -l </proc/swaps)" -eq 1 ]
[ "$($B blockdev --getro /dev/sda)" = 1 ]
[ "$($B blockdev --getro /dev/sda15)" = 1 ]
if [ "$mode" = --check ]; then
    exec /sbin/e2fsck -fn /dev/sda15
fi
# Protect all sibling partitions even while the parent disk is writable.
for node in /sys/class/block/sd*; do
    [ -e "$node/partition" ] || continue
    $B blockdev --setro "/dev/${node##*/}"
done
restore_ro() {
    $B sync
    $B blockdev --setro /dev/sda15
    $B blockdev --setro /dev/sda
}
trap restore_ro EXIT HUP INT TERM
$B blockdev --setrw /dev/sda
$B blockdev --setrw /dev/sda15
set +e
# Preen stops rather than guessing at repairs requiring manual intervention.
/sbin/e2fsck -f -p /dev/sda15 >/run/www/fsck-repair.txt 2>&1
repair_rc=$?
set -e
echo "$repair_rc" >/run/www/fsck-repair-exit.txt
restore_ro
set +e
/sbin/e2fsck -fn /dev/sda15 >/run/www/fsck-after-repair.txt 2>&1
check_rc=$?
set -e
echo "$check_rc" >/run/www/fsck-after-repair-exit.txt
echo done >/run/www/fsck-repair-done.txt
exit "$repair_rc"
