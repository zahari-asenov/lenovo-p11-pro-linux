#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec python3 -m http.server 8000 --bind "${J706F_USB_HOST:-172.16.42.2}" \
    --directory "$J706F_BUILD_ROOT/artifacts"
