#pragma once

#include <stdint.h>

#define TONE_LUT_SIZE 256

void tone_lut_build_y(int lightness, int contrast, uint8_t lut[TONE_LUT_SIZE]);
