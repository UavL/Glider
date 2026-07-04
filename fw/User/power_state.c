#include "power_state.h"

#include <stddef.h>

void power_state_init(power_state_machine_t *state) {
    if (state == NULL)
        return;
    state->current = POWER_STATE_ACTIVE;
    state->last_wake_sources = POWER_WAKE_NONE;
    state->current_suspend_reason = POWER_SUSPEND_NONE;
    state->last_suspend_reason = POWER_SUSPEND_NONE;
    state->suspend_count = 0;
    state->resume_count = 0;
}

power_state_t power_state_current(const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_STATE_ACTIVE;
    return state->current;
}

bool power_state_request_suspend(power_state_machine_t *state,
        power_suspend_reason_t reason) {
    if ((state == NULL) || (state->current != POWER_STATE_ACTIVE))
        return false;
    state->current = POWER_STATE_SUSPENDING;
    state->current_suspend_reason = reason;
    return true;
}

void power_state_mark_suspended(power_state_machine_t *state) {
    if ((state != NULL) && (state->current == POWER_STATE_SUSPENDING)) {
        state->current = POWER_STATE_SUSPENDED;
        state->last_suspend_reason = state->current_suspend_reason;
        state->suspend_count++;
    }
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
    if ((state != NULL) && (state->current == POWER_STATE_RESUMING)) {
        state->current = POWER_STATE_ACTIVE;
        state->current_suspend_reason = POWER_SUSPEND_NONE;
        state->resume_count++;
    }
}

uint32_t power_state_last_wake_sources(const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_WAKE_NONE;
    return state->last_wake_sources;
}

power_suspend_reason_t power_state_current_suspend_reason(
        const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_SUSPEND_NONE;
    return state->current_suspend_reason;
}

power_suspend_reason_t power_state_last_suspend_reason(
        const power_state_machine_t *state) {
    if (state == NULL)
        return POWER_SUSPEND_NONE;
    return state->last_suspend_reason;
}

uint32_t power_state_suspend_count(const power_state_machine_t *state) {
    if (state == NULL)
        return 0;
    return state->suspend_count;
}

uint32_t power_state_resume_count(const power_state_machine_t *state) {
    if (state == NULL)
        return 0;
    return state->resume_count;
}
