#include "autoclear.h"

#include <stdint.h>

#include "config.h"

enum {
    ENCHANTER_REF_HACT = 3200u,
    ENCHANTER_REF_VACT = 2400u,
    ENCHANTER_REF_PIXELS = ENCHANTER_REF_HACT * ENCHANTER_REF_VACT,
};

static uint32_t base_threshold(int threshold) {
    switch (threshold) {
    case AC_THRES_LOW:
        return 2500000u;
    case AC_THRES_HIGH:
        return 25000000u;
    case AC_THRES_MED:
    default:
        return 7500000u;
    }
}

uint32_t autoclear_scaled_threshold(int threshold, uint16_t hact, uint16_t vact) {
    uint32_t base = base_threshold(threshold);

    if ((hact == 0) || (vact == 0))
        return base;

    uint64_t pixels = (uint64_t)hact * (uint64_t)vact;
    uint64_t scaled = ((uint64_t)base * pixels + (ENCHANTER_REF_PIXELS / 2u)) /
            ENCHANTER_REF_PIXELS;

    if (scaled == 0)
        return 1;
    if (scaled > UINT32_MAX)
        return UINT32_MAX;
    return (uint32_t)scaled;
}

// NOTE on sampling: current_damage comes from CSR_DAMAGE_COUNT, which the
// gateware zeroes at every vsync -- it is a per-frame count of transition
// starts, not a running total. A page turn starts all of its transitions in a
// single frame, so a caller polling at 200 ms against a 75 Hz panel only
// observes about one frame in fifteen and undercounts by roughly that factor.
// The scaled thresholds below are calibrated for a complete sample stream
// (AC_THRES_MED works out to ~6 page turns on a 1448x1072 panel, close to a
// Kobo's default), so on the current gateware adaptive mode fires far less
// often than the threshold implies. ui_task therefore arms the fixed-interval
// timer in adaptive mode as well. A cumulative damage register in the gateware
// is the real fix.
bool autoclear_adaptive_update(uint32_t *accumulated_damage,
        uint32_t *last_damage, uint32_t current_damage, int threshold,
        uint16_t hact, uint16_t vact) {
    if ((accumulated_damage == NULL) || (last_damage == NULL))
        return false;

    if (current_damage != 0) {
        uint64_t accumulated = (uint64_t)*accumulated_damage + current_damage;
        uint32_t trigger_threshold =
                autoclear_scaled_threshold(threshold, hact, vact);

        *accumulated_damage = (accumulated > UINT32_MAX) ?
                UINT32_MAX : (uint32_t)accumulated;
        if (*accumulated_damage > trigger_threshold) {
            *accumulated_damage = 0;
            *last_damage = current_damage;
            return true;
        }
    }

    *last_damage = current_damage;
    return false;
}

uint32_t autoclear_fixed_interval_ms(int interval) {
    switch (interval) {
    case AC_1MIN:
        return 60000u;
    case AC_15MIN:
        return 15u * 60000u;
    case AC_5MIN:
    default:
        return 5u * 60000u;
    }
}

int autoclear_toggle_mode(int current_mode, int *previous_mode) {
    if ((current_mode == AC_ADAPT) || (current_mode == AC_FIXED)) {
        if (previous_mode != NULL)
            *previous_mode = current_mode;
        return AC_OFF;
    }

    if ((previous_mode != NULL) &&
            ((*previous_mode == AC_ADAPT) || (*previous_mode == AC_FIXED))) {
        return *previous_mode;
    }

    return AC_ADAPT;
}

void autoclear_reset(uint32_t *accumulated_damage, uint32_t *last_damage) {
    if (accumulated_damage != NULL)
        *accumulated_damage = 0;
    if (last_damage != NULL)
        *last_damage = 0;
}
