#!/bin/sh
# Early generator: firmware charger boots must not start the desktop.
set -eu
[ ! -e /run/j706f-charging-bypass ] || exit 0
for arg in $(cat /proc/cmdline); do
    case "$arg" in
        androidboot.mode=charger)
            mkdir -p "$2"
            ln -sf /etc/systemd/system/j706f-charging.target "$2/default.target"
            exit 0
            ;;
    esac
done
