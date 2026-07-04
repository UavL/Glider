#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "autoclear.h"
#include "config.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_FALSE(expr) ASSERT_TRUE(!(expr))

#define ASSERT_EQ(expected, actual) do { \
    unsigned long long exp__ = (unsigned long long)(expected); \
    unsigned long long act__ = (unsigned long long)(actual); \
    if (exp__ != act__) { \
        printf("ASSERT_EQ failed at %s:%d: expected %llu got %llu\n", \
                __FILE__, __LINE__, exp__, act__); \
        return 1; \
    } \
} while (0)

static int test_thresholds_scale_for_gen1_damage_units(void) {
    ASSERT_EQ(2500000u,
            autoclear_scaled_threshold(AC_THRES_LOW, 3200, 2400));
    ASSERT_EQ(7500000u,
            autoclear_scaled_threshold(AC_THRES_MED, 3200, 2400));
    ASSERT_EQ(25000000u,
            autoclear_scaled_threshold(AC_THRES_HIGH, 3200, 2400));

    ASSERT_EQ(625000u,
            autoclear_scaled_threshold(AC_THRES_LOW, 1600, 1200));
    ASSERT_EQ(1875000u,
            autoclear_scaled_threshold(AC_THRES_MED, 1600, 1200));
    ASSERT_EQ(6250000u,
            autoclear_scaled_threshold(AC_THRES_HIGH, 1600, 1200));
    ASSERT_EQ(505292u,
            autoclear_scaled_threshold(AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(1515875u,
            autoclear_scaled_threshold(AC_THRES_MED, 1448, 1072));
    ASSERT_EQ(5052917u,
            autoclear_scaled_threshold(AC_THRES_HIGH, 1448, 1072));

    return 0;
}

static int test_adaptive_accumulates_damage_samples(void) {
    uint32_t accumulated_damage = 0;
    uint32_t last_damage = 0;

    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            80000, AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(80000u, accumulated_damage);
    ASSERT_EQ(80000u, last_damage);

    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            80000, AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(160000u, accumulated_damage);

    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            90000, AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(250000u, accumulated_damage);

    ASSERT_TRUE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            260000, AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(0u, accumulated_damage);
    ASSERT_EQ(260000u, last_damage);

    return 0;
}

static int test_adaptive_repeated_equal_damage_can_trigger(void) {
    uint32_t accumulated_damage = 0;
    uint32_t last_damage = 0;

    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            150000, AC_THRES_LOW, 1448, 1072));
    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            150000, AC_THRES_LOW, 1448, 1072));
    ASSERT_FALSE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            150000, AC_THRES_LOW, 1448, 1072));
    ASSERT_TRUE(autoclear_adaptive_update(&accumulated_damage, &last_damage,
            150000, AC_THRES_LOW, 1448, 1072));
    ASSERT_EQ(0u, accumulated_damage);

    return 0;
}

static int test_fixed_interval_values_remain_separate(void) {
    ASSERT_EQ(60000u, autoclear_fixed_interval_ms(AC_1MIN));
    ASSERT_EQ(5u * 60000u, autoclear_fixed_interval_ms(AC_5MIN));
    ASSERT_EQ(15u * 60000u, autoclear_fixed_interval_ms(AC_15MIN));
    ASSERT_EQ(5u * 60000u, autoclear_fixed_interval_ms(-1));

    return 0;
}

static int test_toggle_restores_last_non_off_mode(void) {
    int previous = AC_FIXED;

    ASSERT_EQ(AC_OFF, autoclear_toggle_mode(AC_FIXED, &previous));
    ASSERT_EQ(AC_FIXED, previous);
    ASSERT_EQ(AC_FIXED, autoclear_toggle_mode(AC_OFF, &previous));

    previous = AC_ADAPT;
    ASSERT_EQ(AC_OFF, autoclear_toggle_mode(AC_ADAPT, &previous));
    ASSERT_EQ(AC_ADAPT, previous);
    ASSERT_EQ(AC_ADAPT, autoclear_toggle_mode(AC_OFF, &previous));

    previous = -1;
    ASSERT_EQ(AC_ADAPT, autoclear_toggle_mode(AC_OFF, &previous));

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_thresholds_scale_for_gen1_damage_units();
    rc |= test_adaptive_accumulates_damage_samples();
    rc |= test_adaptive_repeated_equal_damage_can_trigger();
    rc |= test_fixed_interval_values_remain_separate();
    rc |= test_toggle_restores_last_non_off_mode();

    return rc;
}
