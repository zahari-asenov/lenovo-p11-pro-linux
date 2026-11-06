#!/usr/bin/env bash
# One source checkout and one external build directory.
J706F_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
J706F_BUILD_ROOT="${J706F_BUILD_ROOT:-$(dirname -- "$J706F_PROJECT_ROOT")/j706f-build}"
J706F_TOOLCHAIN="${J706F_TOOLCHAIN:-$J706F_BUILD_ROOT/toolchain}"
J706F_TOOLCHAIN_MODE="${J706F_TOOLCHAIN_MODE:-auto}"
if [[ "$J706F_TOOLCHAIN_MODE" == auto ]]; then
    if [[ -x "$J706F_TOOLCHAIN/usr/bin/aarch64-linux-gnu-gcc" ]]; then
        J706F_TOOLCHAIN_MODE=bundled
    else
        J706F_TOOLCHAIN_MODE=system
    fi
fi
case "$J706F_TOOLCHAIN_MODE" in
    bundled)
        export PATH="$J706F_TOOLCHAIN/usr/bin:$PATH"
        export LD_LIBRARY_PATH="$J706F_TOOLCHAIN/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export BISON_PKGDATADIR="$J706F_TOOLCHAIN/usr/share/bison"
        export M4="$J706F_TOOLCHAIN/usr/bin/m4"
        ;;
    system) ;;
    *) echo 'J706F_TOOLCHAIN_MODE must be auto, bundled or system.' >&2; return 2 ;;
esac
export J706F_PROJECT_ROOT J706F_BUILD_ROOT J706F_TOOLCHAIN J706F_TOOLCHAIN_MODE
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}" ARCH=arm64
export KBUILD_BUILD_USER=j706f KBUILD_BUILD_HOST=builder
export KBUILD_BUILD_TIMESTAMP='2026-10-15 00:00:00 UTC'
export SOURCE_DATE_EPOCH=1792022400
