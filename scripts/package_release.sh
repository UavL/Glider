#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

version="${1:-}"
release_dir="${2:-}"
[[ -n "$version" && -n "$release_dir" ]] || die "usage: $0 <version> <release-dir>"
validate_release_version "$version"

repo="$(repo_root)"
firmware_dir="$release_dir/firmware"
mkdir -p "$firmware_dir"

write_build_metadata "$release_dir/metadata.txt" "$version"

run_cmd cp "$release_dir/glider_ec_rtos_$version.bin" "$firmware_dir/glider_ec_rtos.bin"
for variant in 8bit-mono 8bit-k3 16bit-mono 16bit-k3; do
    run_cmd cp "$release_dir/caster/$variant/fpga.bit" "$firmware_dir/fpga-$variant.bit"
done
mkdir -p "$firmware_dir/fonts"
for font in font_quicksand_16.bin font_quicksand_20.bin font_quicksand_28.bin; do
    run_cmd cp "$repo/utils/flash_tool/fonts/$font" "$firmware_dir/fonts/$font"
done
run_cmd make -C "$repo/utils/flash_tool/cfggen"
mkdir -p "$firmware_dir/configs"
run_cmd "$repo/utils/flash_tool/cfggen/bin/cfggen" \
    6 1448 1072 75 cvt-rb \
    --out "$firmware_dir/configs/config-6in.bin"
run_cmd "$repo/utils/flash_tool/cfggen/bin/cfggen" \
    13.3 1600 1200 75 cvt-rb2 \
    --out "$firmware_dir/configs/config-13in.bin"
run_cmd cp "$repo/utils/flash_tool/flash.py" "$firmware_dir/flash.py"
