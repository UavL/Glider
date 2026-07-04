#include <stdint.h>
#include <stdio.h>

#include "tone_lut.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_EQ(expected, actual) do { \
    long long exp__ = (long long)(expected); \
    long long act__ = (long long)(actual); \
    if (exp__ != act__) { \
        printf("ASSERT_EQ failed at %s:%d: expected %lld got %lld\n", \
                __FILE__, __LINE__, exp__, act__); \
        return 1; \
    } \
} while (0)

static int test_default_tone_is_identity(void) {
    uint8_t lut[TONE_LUT_SIZE];

    tone_lut_build_y(0, 0, lut);

    ASSERT_EQ(0, lut[0]);
    ASSERT_EQ(1, lut[1]);
    ASSERT_EQ(64, lut[64]);
    ASSERT_EQ(128, lut[128]);
    ASSERT_EQ(255, lut[255]);

    return 0;
}

static int test_lightness_preserves_endpoints_and_moves_midtones(void) {
    uint8_t dark[TONE_LUT_SIZE];
    uint8_t bright[TONE_LUT_SIZE];

    tone_lut_build_y(-3, 0, dark);
    tone_lut_build_y(3, 0, bright);

    ASSERT_EQ(0, dark[0]);
    ASSERT_EQ(255, dark[255]);
    ASSERT_TRUE(dark[128] < 128);

    ASSERT_EQ(0, bright[0]);
    ASSERT_EQ(255, bright[255]);
    ASSERT_TRUE(bright[128] > 128);

    return 0;
}

static int test_contrast_expands_around_midpoint(void) {
    uint8_t lut[TONE_LUT_SIZE];

    tone_lut_build_y(0, 3, lut);

    ASSERT_EQ(0, lut[0]);
    ASSERT_EQ(255, lut[255]);
    ASSERT_TRUE(lut[96] < 96);
    ASSERT_TRUE(lut[160] > 160);

    return 0;
}

static int test_contrast_max_thresholds_midtones(void) {
    uint8_t lut[TONE_LUT_SIZE];

    tone_lut_build_y(0, 6, lut);

    ASSERT_EQ(0, lut[0]);
    ASSERT_EQ(0, lut[96]);
    ASSERT_EQ(255, lut[160]);
    ASSERT_EQ(255, lut[255]);

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_default_tone_is_identity();
    rc |= test_lightness_preserves_endpoints_and_moves_midtones();
    rc |= test_contrast_expands_around_midpoint();
    rc |= test_contrast_max_thresholds_midtones();

    return rc;
}
