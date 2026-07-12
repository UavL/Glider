#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    POWER_STATE_ACTIVE = 0,
    POWER_STATE_SUSPENDING,
    POWER_STATE_SUSPENDED,
    POWER_STATE_RESUMING,
} power_state_t;

typedef enum {
    POWER_WAKE_NONE = 0,
    POWER_WAKE_BUTTON = 1u << 0,
    POWER_WAKE_USB_PD = 1u << 1,
    POWER_WAKE_INPUT = 1u << 2,
    POWER_WAKE_USB = 1u << 3,
    POWER_WAKE_DAMAGE = 1u << 4,
} power_wake_source_t;

typedef enum {
    POWER_SUSPEND_NONE = 0,
    POWER_SUSPEND_USER,
    POWER_SUSPEND_VIDEO_LOSS,
    POWER_SUSPEND_USB,
    POWER_SUSPEND_RETAIN,
} power_suspend_reason_t;

typedef struct {
    power_state_t current;
    uint32_t last_wake_sources;
    power_suspend_reason_t current_suspend_reason;
    power_suspend_reason_t last_suspend_reason;
    uint32_t suspend_count;
    uint32_t resume_count;
} power_state_machine_t;

void power_state_init(power_state_machine_t *state);
power_state_t power_state_current(const power_state_machine_t *state);
bool power_state_request_suspend(power_state_machine_t *state,
        power_suspend_reason_t reason);
void power_state_mark_suspended(power_state_machine_t *state);
void power_state_update_suspend_reason(power_state_machine_t *state,
        power_suspend_reason_t reason);
bool power_state_can_wake(const power_state_machine_t *state,
        uint32_t wake_sources);
bool power_state_request_resume(power_state_machine_t *state,
        uint32_t wake_sources);
void power_state_mark_active(power_state_machine_t *state);
uint32_t power_state_last_wake_sources(const power_state_machine_t *state);
power_suspend_reason_t power_state_current_suspend_reason(
        const power_state_machine_t *state);
power_suspend_reason_t power_state_last_suspend_reason(
        const power_state_machine_t *state);
uint32_t power_state_suspend_count(const power_state_machine_t *state);
uint32_t power_state_resume_count(const power_state_machine_t *state);
