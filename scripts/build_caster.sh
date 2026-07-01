#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/release_common.sh"

ise_host="${1:-}"
version="${2:-}"
release_dir="${3:-}"
[[ -n "$ise_host" && -n "$version" && -n "$release_dir" ]] || die "usage: $0 <ise-host> <version> <release-dir>"
validate_release_version "$version"

repo="$(repo_root)"
caster_out_root="$release_dir/caster"
mkdir -p "$caster_out_root"

for variant in 8bit-mono 8bit-k3 16bit-mono 16bit-k3; do
    run_cmd "$SCRIPT_DIR/build_caster_ise_vm.sh" \
        --host "$ise_host" \
        --source "$repo/Caster" \
        --out "$caster_out_root/$variant" \
        --variant "$variant"
done
