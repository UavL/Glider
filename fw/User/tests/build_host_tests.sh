#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="${TMPDIR:-/tmp}/glider-fw-host-tests"

mkdir -p "$BUILD_DIR"

cc="${CC:-gcc}"
cflags=(
    -DGLIDER_HOST_TEST
    -std=c11
    -Wall
    -Wextra
    -Werror
    -I"$USER_DIR"
)

"$cc" "${cflags[@]}" \
    "$USER_DIR/config.c" \
    "$USER_DIR/ui_menu.c" \
    "$SCRIPT_DIR/test_config_menu.c" \
    -o "$BUILD_DIR/test_config_menu"

"$cc" "${cflags[@]}" \
    "$USER_DIR/osd_font.c" \
    "$SCRIPT_DIR/test_osd_font.c" \
    -o "$BUILD_DIR/test_osd_font"

"$cc" "${cflags[@]}" \
    "$USER_DIR/tone_lut.c" \
    "$SCRIPT_DIR/test_tone_lut.c" \
    -o "$BUILD_DIR/test_tone_lut"

"$BUILD_DIR/test_config_menu"
"$BUILD_DIR/test_osd_font"
"$BUILD_DIR/test_tone_lut"
