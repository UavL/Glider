#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

ise_host="${GLIDER_ISE_VM_HOST:-}"
variant="8bit-mono"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
    --ise-host)
        [[ $# -ge 2 ]] || die "--ise-host requires a value"
        ise_host="$2"
        shift 2
        ;;
    --variant)
        [[ $# -ge 2 ]] || die "--variant requires a value"
        variant="$2"
        shift 2
        ;;
    --help|-h)
        cat <<'USAGE'
usage: scripts/dev_flash_all.sh --ise-host HOST [--variant VARIANT]

Rebuild the MCU firmware and one Caster FPGA bitstream variant, then flash both
to the connected Glider: the MCU over DFU, the bitstream over HID.

Use this when a change spans both sides and they must land together. To iterate
on one side only, use scripts/dev_flash_mcu.sh or scripts/dev_flash_fpga.sh --
this script always rebuilds both, and the gateware build takes several minutes.

The board must be in DFU mode by the time the flashing step starts (hold the
button nearest the USB port while plugging it in). Both builds run first, so
putting it into DFU mode while the gateware builds is fine.
USAGE
        exit 0
        ;;
    -*)
        die "unknown option '$1'"
        ;;
    *)
        die "unexpected argument '$1'"
        ;;
    esac
done

[[ -n "$ise_host" ]] || die "missing ISE VM host; pass --ise-host or set GLIDER_ISE_VM_HOST"
case "$variant" in
    8bit-mono|8bit-k3|16bit-mono|16bit-k3) ;;
    *) die "unknown Caster build variant: $variant" ;;
esac

repo="$(repo_root)"
version="${GLIDER_DEV_VERSION:-dev}"
mcu_dir="$repo/build/dev/mcu"
fpga_dir="$repo/build/dev/caster/$variant"

# Build both before touching the board: the gateware build takes minutes, and a
# failure there should not leave a freshly flashed MCU paired with a stale
# bitstream.
run_cmd "$SCRIPT_DIR/build_mcu.sh" "$version" "$mcu_dir"

run_cmd "$SCRIPT_DIR/build_caster_ise_vm.sh" \
    --host "$ise_host" \
    --source "$repo/Caster" \
    --out "$fpga_dir" \
    --variant "$variant"

log "Flashing; the board must be in DFU mode now"

# flash.py's own MCU path hardcodes ./glider_ec_rtos.bin, so drive dfu-util
# directly here (as dev_flash_mcu.sh does) and let flash.py handle the HID
# transfer only. ':leave' reboots into the application; flash.py already retries
# until the HID interface re-enumerates.
run_cmd dfu-util \
    -a 0 \
    -i 0 \
    -s 0x08000000:leave \
    -D "$mcu_dir/glider_ec_rtos_$version.bin"

run_cmd python3 "$repo/utils/flash_tool/flash.py" \
    --skip-mcu \
    --bitstream "$fpga_dir/fpga.bit" \
    --no-fonts \
    --no-config
