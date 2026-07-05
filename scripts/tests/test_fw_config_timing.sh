#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat >"$tmpdir/test_config_timing.c" <<'TEST_EOF'
#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <string.h>

#include "config_timing.h"

static void test_standard_parser(void) {
    config_timing_standard_t standard;

    assert(config_timing_standard_from_string("cvt-rb2", &standard));
    assert(standard == CONFIG_TIMING_CVT_RB2);
    assert(config_timing_standard_from_string("cvt-rb", &standard));
    assert(standard == CONFIG_TIMING_CVT_RB);
    assert(strcmp(config_timing_standard_name(CONFIG_TIMING_CVT_RB2), "CVT-RBv2") == 0);
    assert(strcmp(config_timing_standard_name(CONFIG_TIMING_CVT_RB), "CVT-RB") == 0);
    assert(!config_timing_standard_from_string("gtf", &standard));
}

static void test_rb2_timing_matches_cfggen(void) {
    config_t cfg = {0};

    assert(config_apply_display_timing(&cfg, 6.0f, 1448, 1072, 75,
            CONFIG_TIMING_CVT_RB2));
    assert(cfg.size_x_mm == 122);
    assert(cfg.size_y_mm == 91);
    assert(cfg.pclk_hz == 127321000);
    assert(cfg.hact == 1448);
    assert(cfg.vact == 1072);
    assert(cfg.hblk == 80);
    assert(cfg.hfp == 8);
    assert(cfg.hsync == 32);
    assert(cfg.vblk == 39);
    assert(cfg.vfp == 25);
    assert(cfg.vsync == 8);
    assert(cfg.tcon_hact == 362);
    assert(cfg.tcon_hfp == 16);
    assert(cfg.tcon_hsync == 2);
    assert(cfg.tcon_hbp == 2);
    assert(cfg.tcon_vact == 1072);
    assert(cfg.tcon_vfp == 11);
    assert(cfg.tcon_vsync == 1);
    assert(cfg.tcon_vbp == 2);
}

static void test_rb_timing_matches_cfggen(void) {
    config_t cfg = {0};

    assert(config_apply_display_timing(&cfg, 6.0f, 1448, 1072, 75,
            CONFIG_TIMING_CVT_RB));
    assert(cfg.pclk_hz == 134000000);
    assert(cfg.hblk == 160);
    assert(cfg.hfp == 48);
    assert(cfg.hsync == 32);
    assert(cfg.vblk == 39);
    assert(cfg.vfp == 3);
    assert(cfg.vsync == 10);
    assert(cfg.tcon_hact == 362);
    assert(cfg.tcon_hfp == 36);
    assert(cfg.tcon_hsync == 2);
    assert(cfg.tcon_hbp == 2);
    assert(cfg.tcon_vfp == 33);
}

static void test_rejects_invalid_inputs(void) {
    config_t cfg = {0};

    assert(!config_apply_display_timing(NULL, 6.0f, 1448, 1072, 75,
            CONFIG_TIMING_CVT_RB2));
    assert(!config_apply_display_timing(&cfg, 0.0f, 1448, 1072, 75,
            CONFIG_TIMING_CVT_RB2));
    assert(!config_apply_display_timing(&cfg, 6.0f, 0, 1072, 75,
            CONFIG_TIMING_CVT_RB2));
    assert(!config_apply_display_timing(&cfg, 6.0f, 1448, 1072, 0,
            CONFIG_TIMING_CVT_RB2));
}

int main(void) {
    test_standard_parser();
    test_rb2_timing_matches_cfggen();
    test_rb_timing_matches_cfggen();
    test_rejects_invalid_inputs();
    return 0;
}
TEST_EOF

gcc -Wall -Wextra -std=c99 -DGLIDER_HOST_TEST \
    -I"$REPO_ROOT/fw/User" \
    "$tmpdir/test_config_timing.c" \
    "$REPO_ROOT/fw/User/config_timing.c" \
    -lm \
    -o "$tmpdir/test_config_timing"

"$tmpdir/test_config_timing"

echo "PASS: firmware config timing"
