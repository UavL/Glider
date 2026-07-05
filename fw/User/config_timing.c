//
// Grimoire
// Copyright 2026 Wenting Zhang
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
//
#ifdef GLIDER_HOST_TEST
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#else
#include "platform.h"
#endif

#include "config_timing.h"

const char *config_timing_standard_name(config_timing_standard_t standard) {
    switch (standard) {
    case CONFIG_TIMING_CVT_RB2:
        return "CVT-RBv2";
    case CONFIG_TIMING_CVT_RB:
        return "CVT-RB";
    default:
        return "unknown";
    }
}

bool config_timing_standard_from_string(const char *text,
        config_timing_standard_t *standard) {
    if ((text == NULL) || (standard == NULL))
        return false;

    if ((strcmp(text, "cvt-rb2") == 0) || (strcmp(text, "rb2") == 0)) {
        *standard = CONFIG_TIMING_CVT_RB2;
        return true;
    }
    if ((strcmp(text, "cvt-rb") == 0) || (strcmp(text, "rb") == 0)) {
        *standard = CONFIG_TIMING_CVT_RB;
        return true;
    }
    return false;
}

static uint8_t cvt_vsync_width(uint16_t x_res, uint16_t y_res) {
    uint32_t x = x_res;
    uint32_t y = y_res;

    if (x * 3u == y * 4u)
        return 4;
    if (x * 9u == y * 16u)
        return 5;
    if (x * 10u == y * 16u)
        return 6;
    if (x * 4u == y * 5u)
        return 7;
    if (x * 9u == y * 15u)
        return 7;
    return 10;
}

static uint32_t round_clock(float raw_hz, uint32_t granularity_hz) {
    return (uint32_t)roundf(raw_hz / (float)granularity_hz) * granularity_hz;
}

bool config_apply_display_timing(config_t *cfg, float size_in,
        uint16_t x_res, uint16_t y_res, uint16_t refresh_hz,
        config_timing_standard_t standard) {
    if ((cfg == NULL) || (size_in <= 0.0f) || (x_res == 0) ||
            (y_res == 0) || (refresh_hz == 0))
        return false;

    if ((standard != CONFIG_TIMING_CVT_RB2) &&
            (standard != CONFIG_TIMING_CVT_RB))
        return false;

    float size_mm = size_in * 25.4f;
    float diag_res = sqrtf(powf((float)x_res, 2.0f) +
            powf((float)y_res, 2.0f));
    cfg->size_x_mm = (uint16_t)roundf(size_mm / diag_res * (float)x_res);
    cfg->size_y_mm = (uint16_t)roundf(size_mm / diag_res * (float)y_res);

    cfg->hact = x_res;
    cfg->vact = y_res;
    if (standard == CONFIG_TIMING_CVT_RB2) {
        cfg->hblk = 80;
        cfg->hfp = 8;
        cfg->hsync = 32;
        cfg->vsync = 8;
    }
    else {
        cfg->hblk = 160;
        cfg->hfp = 48;
        cfg->hsync = 32;
        cfg->vsync = cvt_vsync_width(x_res, y_res);
    }

    float act_lines_time = 1000.0f / (float)refresh_hz - 0.46f;
    cfg->vblk = (uint16_t)((float)cfg->vact / act_lines_time * 0.46f + 1.0f);
    if (standard == CONFIG_TIMING_CVT_RB2) {
        cfg->vfp = cfg->vblk - cfg->vsync - 6;
    }
    else {
        cfg->vfp = 3;
        uint16_t min_vblk = cfg->vfp + cfg->vsync + 6;
        if (cfg->vblk < min_vblk)
            cfg->vblk = min_vblk;
    }

    float raw_pclk_hz = (float)(cfg->hact + cfg->hblk) *
            (float)(cfg->vact + cfg->vblk) * (float)refresh_hz;
    cfg->pclk_hz = (standard == CONFIG_TIMING_CVT_RB2) ?
            round_clock(raw_pclk_hz, 1000) :
            round_clock(raw_pclk_hz, 250000);

    cfg->tcon_hsync = 2;
    cfg->tcon_hbp = 2;
    cfg->tcon_hfp = cfg->hblk / 4 - cfg->tcon_hsync - cfg->tcon_hbp;
    cfg->tcon_hact = x_res / 4;

    cfg->tcon_vsync = 1;
    cfg->tcon_vbp = 2;
    cfg->tcon_vfp = cfg->vblk - cfg->vfp - cfg->tcon_vsync - cfg->tcon_vbp;
    cfg->tcon_vact = y_res;

    return true;
}
