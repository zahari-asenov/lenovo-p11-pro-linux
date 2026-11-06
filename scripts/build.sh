#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
# Refuse in-tree output and aliases into the source tree.
build_path=$(realpath -m "$J706F_BUILD_ROOT")
case "$build_path/" in "$J706F_PROJECT_ROOT/"*) echo 'Build output must be outside the checkout.' >&2; exit 2 ;; esac
command -v "${CROSS_COMPILE}gcc" >/dev/null || { echo 'Cross compiler missing; run scripts/setup-host.sh.' >&2; exit 2; }
mkdir -p "$J706F_BUILD_ROOT/kernel"
if [[ ! -f "$J706F_BUILD_ROOT/kernel/.config" ]]; then
    cp "$J706F_PROJECT_ROOT/configs/j706f.config" "$J706F_BUILD_ROOT/kernel/.config"
fi
if [[ $# -eq 0 ]]; then
    set -- Image.gz qcom/sm7150-lenovo-j706f-power.dtb
fi
host_flags=()
if [[ "$J706F_TOOLCHAIN_MODE" == bundled ]]; then
    host_flags+=("HOSTCFLAGS=-O2 -I$J706F_TOOLCHAIN/usr/include -I$J706F_TOOLCHAIN/usr/include/x86_64-linux-gnu"
        "HOSTLDFLAGS=-L$J706F_TOOLCHAIN/usr/lib/x86_64-linux-gnu"
        'HOSTLDLIBS_extract-cert=/usr/lib/x86_64-linux-gnu/libcrypto.so.3')
fi
make -C "$J706F_PROJECT_ROOT/kernel" O="$J706F_BUILD_ROOT/kernel" \
    -j"${J706F_JOBS:-6}" "${host_flags[@]}" DTC_FLAGS=-@ "$@"
# Private identity is applied only to the generated board DTB, never source.
dtb_configuration=''
for target in "$@"; do
    if [[ "$target" == qcom/sm7150-lenovo-j706f-power.dtb || "$target" == dtbs ]]; then
        dtb_configuration=$(python3 "$J706F_PROJECT_ROOT/scripts/apply-local-dtb.py" \
            --dtb "$J706F_BUILD_ROOT/kernel/arch/arm64/boot/dts/qcom/sm7150-lenovo-j706f-power.dtb")
        printf '%s\n' "$dtb_configuration"
        break
    fi
done
export J706F_DTB_CONFIGURATION="$dtb_configuration"
# Record tool provenance separately from device acceptance.
python3 - "$J706F_PROJECT_ROOT" "$J706F_BUILD_ROOT" "$CROSS_COMPILE" "$@" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
root, build, cross = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def output(args):
    return subprocess.check_output(args, text=True).strip()
config = build / 'kernel/.config'
metadata = {
    'source_commit': output(['git', '-C', str(root), 'rev-parse', 'HEAD']),
    'source_dirty': bool(output(['git', '-C', str(root), 'status', '--porcelain'])),
    'make_targets': sys.argv[4:],
    'cross_compiler': output([cross + 'gcc', '--version']).splitlines()[0],
    'host_compiler': output(['gcc', '--version']).splitlines()[0],
    'make': output(['make', '--version']).splitlines()[0],
    'kernel_config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
    'device_tested': False,
    'dtb_configuration': json.loads(os.environ['J706F_DTB_CONFIGURATION']) if os.environ['J706F_DTB_CONFIGURATION'] else None,
}
(build / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
PY
