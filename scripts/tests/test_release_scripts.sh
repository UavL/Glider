#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_file_contains() {
    local path="$1"
    local pattern="$2"
    local label="$3"

    if ! grep -Eq "$pattern" "$path"; then
        fail "$label: '$path' does not contain pattern '$pattern'"
    fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_file_contains "$REPO_ROOT/.gitmodules" 'path = Caster' "Caster submodule path"
assert_file_contains "$REPO_ROOT/.gitmodules" 'url = https://gitlab.com/zephray/Caster.git/?' "Caster submodule URL"

fake_bin="$tmpdir/bin"
mkdir -p "$fake_bin"
for tool in stm32cubeide ssh scp; do
    printf '#!/usr/bin/env bash\nexit 0\n' >"$fake_bin/$tool"
    chmod +x "$fake_bin/$tool"
done

release_log="$tmpdir/release.log"
release_root="$tmpdir/release"

(
    export PATH="$fake_bin:$PATH"
    export DRY_RUN=1
    export RELEASE_DRY_RUN_LOG="$release_log"
    export RELEASE_ROOT="$release_root"
    "$REPO_ROOT/scripts/release.sh" --ise-host 192.168.56.101 0.1-task2
)

assert_file_contains "$release_log" "stm32cubeide .*org.eclipse.cdt.managedbuilder.core.headlessbuild .*glider_ec_rtos/Debug" "headless CubeIDE MCU build"
assert_file_contains "$release_log" "git -C .*/Glider submodule update --init --recursive" "recursive submodule update"
assert_file_contains "$release_log" "build_caster_ise_vm.sh --host 192.168.56.101 --source .*/Glider/Caster --out .*/0.1-task2/caster --variants 8bit-mono,8bit-k3,16bit-mono,16bit-k3" "single Caster VM build for all release variants"
assert_file_contains "$release_log" "package_release.sh 0.1-task2 .*/0.1-task2" "release packaging"

metadata="$release_root/0.1-task2/metadata.txt"
[[ -f "$metadata" ]] || fail "release metadata was not generated"
assert_file_contains "$metadata" '^version=0.1-task2$' "metadata version"
assert_file_contains "$metadata" '^glider_revision=[0-9a-f]{40}$' "metadata Glider revision"
assert_file_contains "$metadata" '^caster_revision=[0-9a-f]{40}$' "metadata Caster revision"
for variant in 8bit-mono 8bit-k3 16bit-mono 16bit-k3; do
    assert_file_contains "$release_log" "cp .*/0.1-task2/caster/$variant/fpga.bit .*/0.1-task2/flash_tool/fpga-$variant.bit" "packaged bitstream for $variant"
done
assert_file_contains "$release_log" "python3 .*/tools/fonts/generate_quicksand_fonts.py --out-dir .*/0.1-task2/flash_tool/fonts" "generated Quicksand release fonts"
if grep -Eq "cp .*/utils/flash_tool/font_24x40.bin .*/0.1-task2/flash_tool/font_24x40.bin" "$release_log"; then
    fail "release should not package the legacy font_24x40.bin"
fi
if grep -Eq "cp .*/0.1-task2/caster/8bit-mono/fpga.bit .*/0.1-task2/flash_tool/fpga.bit" "$release_log"; then
    fail "release should not package an ambiguous fpga.bit compatibility copy"
fi

ise_vm_log="$tmpdir/ise-vm.log"
(
    export DRY_RUN=1
    "$REPO_ROOT/scripts/build_caster_ise_vm.sh" \
        --host 192.168.56.101 \
        --source "$REPO_ROOT/Caster" \
        --out "$tmpdir/caster" \
        --variant 8bit-mono
) >"$ise_vm_log"
assert_file_contains "$ise_vm_log" "sshpass -p xilinx ssh " "ISE VM helper passes default SSH password"
assert_file_contains "$ise_vm_log" "sshpass -p xilinx scp " "ISE VM helper passes default SCP password"

no_tool_log="$tmpdir/no-tool-mcu.log"
(
    export PATH="/usr/bin:/bin"
    export DRY_RUN=1
    export RELEASE_DRY_RUN_LOG="$no_tool_log"
    "$REPO_ROOT/scripts/build_mcu.sh" 0.1-task2 "$tmpdir/no-tool-release"
)
assert_file_contains "$no_tool_log" "stm32cubeide .*org.eclipse.cdt.managedbuilder.core.headlessbuild .*glider_ec_rtos/Debug" "dry-run MCU build without STM32CubeIDE installed"

dev_mcu_log="$tmpdir/dev-mcu.log"
(
    export DRY_RUN=1
    "$REPO_ROOT/scripts/dev_flash_mcu.sh"
) >"$dev_mcu_log" 2>&1
assert_file_contains "$dev_mcu_log" "build_mcu.sh dev .*/Glider/build/dev/mcu" "dev MCU script rebuilds firmware"
assert_file_contains "$dev_mcu_log" "dfu-util -a 0 -i 0 -s 0x08000000:leave -D .*/Glider/build/dev/mcu/glider_ec_rtos_dev.bin" "dev MCU script flashes built firmware"

dev_fpga_log="$tmpdir/dev-fpga.log"
(
    export DRY_RUN=1
    "$REPO_ROOT/scripts/dev_flash_fpga.sh" --ise-host 192.168.56.101 --variant 16bit-k3
) >"$dev_fpga_log" 2>&1
assert_file_contains "$dev_fpga_log" "build_caster_ise_vm.sh --host 192.168.56.101 --source .*/Glider/Caster --out .*/Glider/build/dev/caster/16bit-k3 --variant 16bit-k3" "dev FPGA script builds one variant"
assert_file_contains "$dev_fpga_log" "python3 .*/Glider/utils/flash_tool/flash.py --skip-mcu --bitstream .*/Glider/build/dev/caster/16bit-k3/fpga.bit --no-fonts" "dev FPGA script transfers only selected bitstream"

echo "PASS: Glider release dry-run"
