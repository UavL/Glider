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
#pragma once

#include <stdbool.h>

#include "config.h"

typedef enum {
    CONFIG_TIMING_CVT_RB2,
    CONFIG_TIMING_CVT_RB,
} config_timing_standard_t;

const char *config_timing_standard_name(config_timing_standard_t standard);
bool config_timing_standard_from_string(const char *text,
        config_timing_standard_t *standard);
bool config_apply_display_timing(config_t *cfg, float size_in,
        uint16_t x_res, uint16_t y_res, uint16_t refresh_hz,
        config_timing_standard_t standard);
