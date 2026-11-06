#!/usr/bin/env bash
# Check dependencies by default. Install only when explicitly requested.
set -euo pipefail
case "${1:-}" in
    --install)
        [[ $# -eq 1 ]] || exit 2
        command -v apt-get >/dev/null || { echo 'Automatic installation supports Debian/Ubuntu only.' >&2; exit 2; }
        sudo apt-get update
        sudo apt-get install --no-install-recommends build-essential gcc-aarch64-linux-gnu \
            libc6-dev-arm64-cross bc bison flex libssl-dev libelf-dev pkg-config \
            python3 python3-gi python3-yaml gsettings-desktop-schemas device-tree-compiler cpio \
            e2fsprogs git xz-utils
        ;;
    '') [[ $# -eq 0 ]] || exit 2 ;;
    *) echo 'Usage: scripts/setup-host.sh [--install]' >&2; exit 2 ;;
esac
missing=0
for name in make gcc aarch64-linux-gnu-gcc bc bison flex pkg-config python3 dtc fdtget fdtput cpio debugfs e2fsck git xz; do
    if ! command -v "$name" >/dev/null; then echo "Missing: $name" >&2; missing=1; fi
done
if ! python3 -c 'import gi; from gi.repository import Gio' 2>/dev/null; then
    echo 'Missing: Python GObject/Gio (python3-gi)' >&2; missing=1
fi
if [[ "$missing" -ne 0 ]]; then
    echo 'Install the documented host dependencies, or run scripts/setup-host.sh --install.' >&2
    exit 1
fi
printf 'Host tools found. Compiler: '
aarch64-linux-gnu-gcc -dumpfullversion
printf 'Headers/libraries and ARM64 compilation are checked by scripts/build.sh.\n'
