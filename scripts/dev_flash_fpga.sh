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
usage: scripts/dev_flash_fpga.sh --ise-host HOST [--variant VARIANT]

Build one Caster FPGA bitstream variant through the ISE VM and transfer only
that bitstream to the connected Glider over HID.
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
out_dir="$repo/build/dev/caster/$variant"

run_cmd "$SCRIPT_DIR/build_caster_ise_vm.sh" \
    --host "$ise_host" \
    --source "$repo/Caster" \
    --out "$out_dir" \
    --variant "$variant"

run_cmd python3 "$repo/utils/flash_tool/flash.py" \
    --skip-mcu \
    --bitstream "$out_dir/fpga.bit" \
    --no-fonts
