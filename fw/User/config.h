//
// Grimoire
// Copyright 2025 Wenting Zhang
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
#pragma once

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#include "caster.h"

#define BITSTREAM_NAME_MAX  40

#define CONFIG_SCHEMA_VERSION       2u
#define CONFIG_BUTTON_BINDING_COUNT 6

#define INPUT_SEL_AUTO      0
#define INPUT_SEL_TMDS      1
#define INPUT_SEL_DP        2

typedef enum {
    ACT_PREV_MODE = 0,
    ACT_NEXT_MODE,
    ACT_MODE_BROWSING,
    ACT_MODE_WATCHING,
    ACT_MODE_TYPING,
    ACT_MODE_READING,
    ACT_CLEAR,
    ACT_TOGGLE_AC,
    ACT_OPEN_SETTINGS,
    ACT_POFF,
    ACT_INPUT_AUTO,
    ACT_INPUT_TMDS,
    ACT_INPUT_DP,
    ACT_COUNT
} button_action_t;

typedef enum {
    AC_OFF = 0,
    AC_ADAPT,
    AC_FIXED,
    AC_MODE_COUNT
} autoclear_mode_t;

typedef enum {
    AC_1MIN = 0,
    AC_5MIN,
    AC_15MIN,
    AC_INTERVAL_COUNT
} autoclear_interval_t;

typedef enum {
    AC_THRES_HIGH = 0,
    AC_THRES_MED,
    AC_THRES_LOW,
    AC_THRES_COUNT
} autoclear_threshold_t;

typedef struct {
    uint32_t pclk_hz; // pixel clock
    uint8_t hfp;
    uint8_t vfp;
    uint8_t hsync;
    uint8_t vsync;
    uint16_t hact;
    uint16_t hblk;
    uint16_t vact;
    uint16_t vblk;
    uint16_t size_x_mm; // horizontal screen size
    uint16_t size_y_mm; // vertical screen size
    uint8_t mfg_week;
    uint8_t mfg_year;
    float vcom;
    float vgh;
    // TCON configurations
    uint8_t tcon_vfp;
    uint8_t tcon_vsync;
    uint8_t tcon_vbp;
    uint16_t tcon_vact;
    uint8_t tcon_hfp;
    uint8_t tcon_hsync;
    uint8_t tcon_hbp;
    uint16_t tcon_hact;
    uint8_t mirror;
    // Input selection (0 - Auto, 1 - TMDS, 2 - DP)
    uint8_t input_sel;
    // without 'aligned' attribute, the first 2 bytes of bitstream will be
    // overwritten when loading 'legacy' configs (w/o 'bitstream' field),
    // because their config_t padded with 2 extra bytes at the end
    char bitstream[BITSTREAM_NAME_MAX] __attribute__((aligned(4)));
    uint32_t schema_version;
    int button_actions[CONFIG_BUTTON_BINDING_COUNT];
    int update_mode;
    int lightness;
    int contrast;
    int reserved_tone;
    int autoclear_mode;
    int autoclear_interval;
    int autoclear_threshold;
    int osd_scale_2x;
} config_t;

extern config_t config;

void config_init(void);
void config_reset_button_actions(void);
void config_validate_loaded(size_t loaded_size);
void config_load(void);
void config_save(void);
