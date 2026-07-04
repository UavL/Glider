#include "tone_lut.h"

static float clampf_local(float value, float lo, float hi) {
    if (value < lo)
        return lo;
    if (value > hi)
        return hi;
    return value;
}

static int lightness_index(int value) {
    if (value < -3)
        return 0;
    if (value > 3)
        return 6;
    return value + 3;
}

static int contrast_index(int value) {
    if (value < -1)
        return 0;
    if (value > 6)
        return 7;
    return value + 1;
}

void tone_lut_build_y(int lightness, int contrast, uint8_t lut[TONE_LUT_SIZE]) {
    static const float lightness_lut[7] = {
        0.0f, 0.3f, 0.6f, 1.0f, 1.3f, 1.6f, 2.0f
    };
    static const float contrast_lut[8] = {
        0.8f, 1.0f, 1.35f, 1.8f, 2.7f, 5.0f, 12.0f, 255.0f
    };

    float lightness_factor = lightness_lut[lightness_index(lightness)];
    float contrast_factor = contrast_lut[contrast_index(contrast)];
    float bias = lightness_factor - 1.0f;

    for (int i = 0; i < TONE_LUT_SIZE; i++) {
        float norm = (float)i / 255.0f;
        float contrasted = clampf_local(0.5f + (norm - 0.5f) * contrast_factor,
                0.0f, 1.0f);
        float shaped = contrasted + bias * (contrasted - contrasted * contrasted);
        float clamped = clampf_local(shaped, 0.0f, 1.0f);
        lut[i] = (uint8_t)(clamped * 255.0f + 0.5f);
    }
}
