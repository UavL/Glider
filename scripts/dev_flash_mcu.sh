#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

version="${GLIDER_DEV_VERSION:-dev}"
out_dir="$(repo_root)/build/dev/mcu"

run_cmd "$SCRIPT_DIR/build_mcu.sh" "$version" "$out_dir"
flash_mcu_dfu "$out_dir/glider_ec_rtos_$version.bin"
