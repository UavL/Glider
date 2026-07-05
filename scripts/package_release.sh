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
for variant in 8bit-mono 8bit-k3 16bit-mono 16bit-k3; do
    run_cmd cp "$release_dir/caster/$variant/fpga.bit" "$flash_dir/fpga-$variant.bit"
done
run_cmd python3 "$repo/tools/fonts/generate_quicksand_fonts.py" --out-dir "$flash_dir/fonts"
run_cmd make -C "$repo/utils/flash_tool/cfggen"
mkdir -p "$flash_dir/configs"
run_cmd "$repo/utils/flash_tool/cfggen/bin/cfggen" \
    6 1448 1072 75 cvt-rb \
    --out "$flash_dir/configs/config-6in.bin"
run_cmd "$repo/utils/flash_tool/cfggen/bin/cfggen" \
    13.3 1600 1200 75 cvt-rb2 \
    --out "$flash_dir/configs/config-13in.bin"
run_cmd cp "$repo/utils/flash_tool/flash.py" "$flash_dir/flash.py"
