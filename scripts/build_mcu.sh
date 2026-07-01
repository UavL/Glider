#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

version="${1:-}"
release_dir="${2:-}"
[[ -n "$version" && -n "$release_dir" ]] || die "usage: $0 <version> <release-dir>"
validate_release_version "$version"

repo="$(repo_root)"
if [[ "${DRY_RUN:-0}" != "1" && ! -f "$repo/fw/User/tinyusb/src/tusb.h" ]]; then
    die "TinyUSB submodule is missing; run git submodule update --init --recursive"
fi

ide_bin="$(find_stm32cubeide_executable || true)"
if [[ -z "$ide_bin" ]]; then
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        ide_bin="${STM32CUBEIDE_BIN:-stm32cubeide}"
    else
        die "could not find STM32CubeIDE; set STM32CUBEIDE_BIN"
    fi
fi

workspace="$repo/build/stm32-workspace"
mkdir -p "$release_dir"

run_cmd "$ide_bin" \
    -nosplash \
    --launcher.suppressErrors \
    -application org.eclipse.cdt.managedbuilder.core.headlessbuild \
    -data "$workspace" \
    -import "$repo/fw" \
    -cleanBuild glider_ec_rtos/Debug

run_cmd cp "$repo/fw/Debug/glider_ec_rtos.bin" "$release_dir/glider_ec_rtos_$version.bin"
