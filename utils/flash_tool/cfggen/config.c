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
#include <stdint.h>
#include "config.h"

config_t config;

void config_init(void) {
    // Set default values
    config.size_x_mm = 270;
    config.size_y_mm = 203;
    config.mfg_week = 1;
    config.mfg_year = 0x20;

    // 1448x1072 @ 75
    config.pclk_hz = 127320000;
    config.hact = 1448;
    config.vact = 1072;
    config.hblk = 80;
    config.hfp = 8;
    config.hsync = 32;
    config.vblk = 39;
    config.vfp = 25;
    config.vsync = 8;

    config.tcon_vfp = 11;
    config.tcon_vsync = 1;
    config.tcon_vbp = 2;
    config.tcon_vact = 1072;
    // HFP + HSYNC + HBP = Incoming HBLK / 4
    config.tcon_hfp = 17;
    config.tcon_hsync = 2;
    config.tcon_hbp = 1;
    config.tcon_hact = 362;

    config.vcom = -2.30f;
    config.vgh = 25.0f;

    //config.mirror = 1;

    config.input_sel = INPUT_SEL_AUTO;
}
