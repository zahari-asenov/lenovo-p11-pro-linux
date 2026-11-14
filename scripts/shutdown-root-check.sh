#!/bin/busybox sh
# Marker-only exitrd proof. Never repair, mount internal storage or auto-reboot.
# The earlier repair-capable experiment is retained in the private research archive.
[ "$$" -eq 1 ] || exit 90
# systemd-shutdown supplies console stdio before exec; retain it.
# Reopening /dev/console here could terminate PID1 on redirection failure.
export PATH=/bin:/sbin
printf '\nJ706F_EXITRD_ENTERED pid=%s verb=%s\n' "$$" "${1:-missing}"
printf 'RAM handoff reached. No filesystem check or repair has been run.\n'
printf 'Do not run fsck until all internal mounts and swap are verified absent.\n'
printf 'The old root may still be mounted under /oldroot.\n'
# Keep visible evidence and a recovery console, even if the child shell exits.
# No disk-dependent receipt, guessed repair or silent forced reboot.
while :; do
    /bin/busybox sh -i
    printf '\nRecovery console exited; opening it again. No automatic reboot.\n'
    /bin/busybox sleep 1
done
