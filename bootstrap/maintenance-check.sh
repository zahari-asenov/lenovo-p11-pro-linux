# Appended after USB setup. No internal mounts; assessment is read-only.
# A repair listener is inserted only by an explicitly opted-in package.
B=/bin/busybox-ui
say 'J706F filesystem maintenance: read-only assessment only'
for node in /sys/class/block/sd*; do
    [ -e "$node/dev" ] || continue
    $B blockdev --setro "/dev/${node##*/}"
done
assess() {
    [ -f /etc/j706f-root.conf ] || return 90
    . /etc/j706f-root.conf
    [ -n "${J706F_SERIAL:-}" ] && [ "$J706F_SERIAL" != CONFIGURE_DEVICE_SERIAL ] || return 90
    [ -n "${J706F_PARTUUID:-}" ] && [ -n "${J706F_BYTES:-}" ] || return 90
    grep -Fqw "androidboot.serialno=$J706F_SERIAL" /proc/cmdline || return 90
    tries=0
    while [ ! -b /dev/sda15 ]; do
        tries=$((tries + 1))
        [ "$tries" -lt 30 ] || return 91
        sleep 1
    done
    grep -Fqx "PARTUUID=$J706F_PARTUUID" /sys/class/block/sda15/uevent || return 92
    grep -qx 'PARTNAME=userdata' /sys/class/block/sda15/uevent || return 93
    [ "$($B blockdev --getsize64 /dev/sda15)" = "$J706F_BYTES" ] || return 94
    # Refuse any internal filesystem mount, regardless of mount source alias.
    for node in /sys/class/block/sd*; do
        [ -e "$node/dev" ] || continue
        $B blockdev --setro "/dev/${node##*/}" || return 95
        dev=$(cat "$node/dev")
        while read -r id parent mounted_dev rest; do
            [ "$mounted_dev" != "$dev" ] || return 96
        done </proc/self/mountinfo
    done
    [ "$($B wc -l </proc/swaps)" -eq 1 ] || return 97
    [ "$($B blockdev --getro /dev/sda15)" = 1 ] || return 98
    cat /proc/mounts >/run/www/maintenance-mounts.txt
    cat /proc/swaps >/run/www/maintenance-swaps.txt
    /sbin/e2fsck -fn /dev/sda15 >/run/www/fsck-readonly.txt 2>&1
}
assess
assessment_rc=$?
echo "$assessment_rc" >/run/www/fsck-exit.txt
say 'Read-only filesystem assessment completed; see fsck-readonly.txt and fsck-exit.txt'
# Capture only the expected root geometry; all output stays in RAM.
metadata_u32() {
    value=$($B od -An -tu4 -N4 -j "$1" /run/www/root-metadata-prefix.bin) || return 1
    set -- $value
    [ "$#" -eq 1 ] || return 1
    printf '%s\n' "$1"
}
metadata_capture() {
    $B rm -f /run/www/metadata-ready.txt || return 1
    [ "$assessment_rc" = 0 ] || [ "$assessment_rc" = 4 ] || return 1
    [ "$($B blockdev --getro /dev/sda)" = 1 ] || return 1
    [ "$($B blockdev --getro /dev/sda15)" = 1 ] || return 1
    $B dd if=/dev/sda15 of=/run/www/root-metadata-prefix.bin bs=4096 count=16 || return 1
    [ "$($B wc -c < /run/www/root-metadata-prefix.bin)" -eq 65536 ] || return 1
    magic=$($B od -An -tu2 -N2 -j 1080 /run/www/root-metadata-prefix.bin) || return 1
    desc=$($B od -An -tu2 -N2 -j 1278 /run/www/root-metadata-prefix.bin) || return 1
    [ "$magic" -eq 61267 ] && [ "$desc" -eq 64 ] || return 1
    [ "$(metadata_u32 1048)" -eq 2 ] || return 1
    [ "$(metadata_u32 1028)" -eq 26856659 ] || return 1
    [ "$(metadata_u32 1360)" -eq 0 ] || return 1
    [ "$(metadata_u32 1044)" -eq 0 ] || return 1
    [ "$(metadata_u32 1056)" -eq 32768 ] || return 1
    [ "$(metadata_u32 1060)" -eq 32768 ] || return 1
    [ "$(metadata_u32 1064)" -eq 8192 ] || return 1
    incompat=$(metadata_u32 1120) || return 1
    [ "$((incompat & 16))" -eq 0 ] && [ "$((incompat & 128))" -ne 0 ] || return 1
    # 820 groups * 64 bytes fit in primary descriptor blocks 1..13.
    : >/run/www/root-metadata-locations.txt || return 1
    for group in 33 419 460 463; do
        for kind in block inode; do
            [ "$kind" = block ] || [ "$group" = 33 ] || continue
            offset=$((4096 + group * 64))
            [ "$kind" = block ] || offset=$((offset + 4))
            lo=$(metadata_u32 "$offset") || return 1
            hi=$(metadata_u32 "$((offset + 32))") || return 1
            [ "$hi" -eq 0 ] && [ "$lo" -gt 0 ] && [ "$lo" -lt 26856659 ] || return 1
            output=/run/www/root-group${group}-${kind}-bitmap.bin
            $B dd if=/dev/sda15 of="$output" bs=4096 skip="$lo" count=1 || return 1
            [ "$($B wc -c < "$output")" -eq 4096 ] || return 1
            printf '%s %s %s\n' "$group" "$kind" "$lo" >>/run/www/root-metadata-locations.txt || return 1
        done
    done
    (cd /run/www && $B sha256sum root-metadata-prefix.bin root-metadata-locations.txt root-group33-block-bitmap.bin root-group33-inode-bitmap.bin root-group419-block-bitmap.bin root-group460-block-bitmap.bin root-group463-block-bitmap.bin >root-metadata-sha256.txt && $B sha256sum -c root-metadata-sha256.txt) || return 1
    printf 'ready\n' >/run/www/metadata-ready.txt
}
metadata_capture >/run/www/root-metadata-capture.txt 2>&1
echo "$?" >/run/www/root-metadata-exit.txt
# Visible local console; no display-power or brightness changes.
(
    while :; do
        if [ -c /dev/tty1 ]; then
            printf '\nJ706F RAM maintenance root shell; disks remain read-only.\n' >/dev/tty1
            /bin/busybox-ui setsid -c /bin/sh -i </dev/tty1 >/dev/tty1 2>&1
        fi
        sleep 1
    done
) &
# Local USB serial console for reviewed follow-up commands. Disks stay RO.
(
    while :; do
        if [ -c /dev/ttyGS0 ]; then
            printf '\nJ706F maintenance shell; internal disks read-only.\n' >/dev/ttyGS0
            setsid -c /bin/sh -i </dev/ttyGS0 >/dev/ttyGS0 2>&1
        fi
        sleep 2
    done
) &
# J706F_ROOT_REPAIR_HTTP
while :; do
    dmesg >/run/www/dmesg.txt
    cp /run/init.log /run/www/init.txt
    sleep 3
done
