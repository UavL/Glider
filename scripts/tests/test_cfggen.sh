#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_contains() {
    local output="$1"
    local pattern="$2"
    local label="$3"

    if ! grep -Eq "$pattern" <<<"$output"; then
        fail "$label: output does not contain '$pattern'"
    fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

gcc -Wall -std=c99 \
    "$REPO_ROOT/utils/flash_tool/cfggen/main.c" \
    "$REPO_ROOT/utils/flash_tool/cfggen/config.c" \
    -lm \
    -o "$tmpdir/cfggen"

rb2_output="$(
    cd "$tmpdir"
    ./cfggen 6 1448 1072 75 cvt-rb2
)"
assert_contains "$rb2_output" "Timing standard: CVT-RBv2" "explicit RBv2 standard"
assert_contains "$rb2_output" "PCLK: 127321000 Hz" "RBv2 pclk compatibility"
assert_contains "$rb2_output" "HBLK: 80" "RBv2 horizontal blanking"
assert_contains "$rb2_output" "HFP:  8" "RBv2 horizontal front porch"
assert_contains "$rb2_output" "VFP:  25" "RBv2 vertical front porch"

rb2_default_output="$(
    cd "$tmpdir"
    ./cfggen 6 1448 1072 75
)"
assert_contains "$rb2_default_output" "Timing standard: CVT-RBv2" "default timing standard remains RBv2"
assert_contains "$rb2_default_output" "PCLK: 127321000 Hz" "default pclk compatibility"

rb_output="$(
    cd "$tmpdir"
    ./cfggen 6 1448 1072 75 cvt-rb
)"
assert_contains "$rb_output" "Timing standard: CVT-RB" "explicit RB standard"
assert_contains "$rb_output" "PCLK: 134000000 Hz" "RB pclk"
assert_contains "$rb_output" "HBLK: 160" "RB horizontal blanking"
assert_contains "$rb_output" "HFP:  48" "RB horizontal front porch"
assert_contains "$rb_output" "HSW:  32" "RB horizontal sync"
assert_contains "$rb_output" "VFP:  3" "RB vertical front porch"

out_file="$tmpdir/config-6in.bin"
out_output="$(
    cd "$tmpdir"
    ./cfggen 6 1448 1072 75 cvt-rb --out "$out_file"
)"
assert_contains "$out_output" "Output: $out_file" "cfggen output path"
[[ -s "$out_file" ]] || fail "cfggen did not write output file"

echo "PASS: cfggen timing standards"
