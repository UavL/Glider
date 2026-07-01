#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

force="${RELEASE_FORCE:-0}"
ise_host="${GLIDER_ISE_VM_HOST:-}"
version=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
    --force|-f)
        force=1
        shift
        ;;
    --dry-run)
        DRY_RUN=1
        export DRY_RUN
        shift
        ;;
    --ise-host)
        [[ $# -ge 2 ]] || die "--ise-host requires a value"
        ise_host="$2"
        shift 2
        ;;
    --help|-h)
        cat <<'USAGE'
usage: scripts/release.sh --ise-host HOST [--force] [--dry-run] <version>

Build a Glider release with the Caster bitstream built through the Xilinx ISE VM.
Set GLIDER_ISE_VM_HOST instead of --ise-host if preferred.
USAGE
        exit 0
        ;;
    -*)
        die "unknown option '$1'"
        ;;
    *)
        [[ -z "$version" ]] || die "unexpected argument '$1'"
        version="$1"
        shift
        ;;
    esac
done

[[ -n "$version" ]] || die "missing release version"
[[ -n "$ise_host" ]] || die "missing ISE VM host; pass --ise-host or set GLIDER_ISE_VM_HOST"
validate_release_version "$version"

release_root="${RELEASE_ROOT:-$(repo_root)/build/release}"
release_dir="$release_root/$version"
prepare_release_dir "$release_dir" "$force"
log_dir="$release_dir/logs"
mkdir -p "$log_dir"

log "Starting Glider release $version"
log "Output directory: $release_dir"

ensure_submodules

run_logged_step "MCU build" "$log_dir/01_mcu.log" \
    "$SCRIPT_DIR/build_mcu.sh" "$version" "$release_dir"

run_logged_step "Caster VM build" "$log_dir/02_caster.log" \
    "$SCRIPT_DIR/build_caster.sh" "$ise_host" "$version" "$release_dir"

run_logged_step "release packaging" "$log_dir/03_package.log" \
    "$SCRIPT_DIR/package_release.sh" "$version" "$release_dir"

log "Release complete: $release_dir"
