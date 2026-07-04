#include "power_state.h"

#include <stddef.h>

void power_state_init(power_state_machine_t *state) {
    if (state == NULL)
        return;
    state->current = POWER_STATE_ACTIVE;
    state->last_wake_sources = POWER_WAKE_NONE;
}

power_state_t power_state_current(const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_STATE_ACTIVE;
    return state->current;
}

bool power_state_request_suspend(power_state_machine_t *state) {
    if ((state == NULL) || (state->current != POWER_STATE_ACTIVE))
        return false;
    state->current = POWER_STATE_SUSPENDING;
    return true;
}

void power_state_mark_suspended(power_state_machine_t *state) {
    if ((state != NULL) && (state->current == POWER_STATE_SUSPENDING))
        state->current = POWER_STATE_SUSPENDED;
}

bool power_state_can_wake(const power_state_machine_t *state,
        uint32_t wake_sources) {
    return (state != NULL) &&
            (state->current == POWER_STATE_SUSPENDED) &&
            (wake_sources != POWER_WAKE_NONE);
}

bool power_state_request_resume(power_state_machine_t *state,
        uint32_t wake_sources) {
    if (!power_state_can_wake(state, wake_sources))
        return false;
    state->current = POWER_STATE_RESUMING;
    state->last_wake_sources = wake_sources;
    return true;
}

void power_state_mark_active(power_state_machine_t *state) {
    if ((state != NULL) && (state->current == POWER_STATE_RESUMING))
        state->current = POWER_STATE_ACTIVE;
}

uint32_t power_state_last_wake_sources(const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_WAKE_NONE;
    return state->last_wake_sources;
}
