#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

version="${1:-}"
release_dir="${2:-}"
[[ -n "$version" && -n "$release_dir" ]] || die "usage: $0 <version> <release-dir>"
validate_release_version "$version"

repo="$(repo_root)"
flash_dir="$release_dir/flash_tool"
mkdir -p "$flash_dir"

write_build_metadata "$release_dir/metadata.txt" "$version"

run_cmd cp "$release_dir/glider_ec_rtos_$version.bin" "$flash_dir/glider_ec_rtos.bin"
run_cmd cp "$release_dir/caster/fpga.bit" "$flash_dir/fpga.bit"
run_cmd cp "$repo/utils/flash_tool/font_24x40.bin" "$flash_dir/font_24x40.bin"
run_cmd cp "$repo/utils/flash_tool/main.py" "$flash_dir/main.py"
run_cmd cp "$repo/utils/flash_tool/flash.py" "$flash_dir/flash.py"
