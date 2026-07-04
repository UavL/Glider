#include <stdbool.h>
#include <stdio.h>

#include "power_state.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_FALSE(expr) ASSERT_TRUE(!(expr))

#define ASSERT_EQ(expected, actual) do { \
    if ((expected) != (actual)) { \
        printf("ASSERT_EQ failed at %s:%d: expected %d got %d\n", \
                __FILE__, __LINE__, (int)(expected), (int)(actual)); \
        return 1; \
    } \
} while (0)

static int test_suspend_resume_transitions_are_ordered(void) {
    power_state_machine_t state;

    power_state_init(&state);
    ASSERT_EQ(POWER_STATE_ACTIVE, power_state_current(&state));
    ASSERT_EQ(POWER_SUSPEND_NONE, power_state_current_suspend_reason(&state));
    ASSERT_EQ(POWER_SUSPEND_NONE, power_state_last_suspend_reason(&state));
    ASSERT_EQ(0, power_state_suspend_count(&state));
    ASSERT_EQ(0, power_state_resume_count(&state));

    ASSERT_TRUE(power_state_request_suspend(&state, POWER_SUSPEND_USER));
    ASSERT_EQ(POWER_STATE_SUSPENDING, power_state_current(&state));
    ASSERT_EQ(POWER_SUSPEND_USER, power_state_current_suspend_reason(&state));
    ASSERT_FALSE(power_state_request_suspend(&state, POWER_SUSPEND_VIDEO_LOSS));

    power_state_mark_suspended(&state);
    ASSERT_EQ(POWER_STATE_SUSPENDED, power_state_current(&state));
    ASSERT_EQ(POWER_SUSPEND_USER, power_state_current_suspend_reason(&state));
    ASSERT_EQ(POWER_SUSPEND_USER, power_state_last_suspend_reason(&state));
    ASSERT_EQ(1, power_state_suspend_count(&state));
    ASSERT_EQ(0, power_state_resume_count(&state));

    ASSERT_TRUE(power_state_request_resume(&state, POWER_WAKE_BUTTON));
    ASSERT_EQ(POWER_STATE_RESUMING, power_state_current(&state));
    ASSERT_FALSE(power_state_request_resume(&state, POWER_WAKE_BUTTON));

    power_state_mark_active(&state);
    ASSERT_EQ(POWER_STATE_ACTIVE, power_state_current(&state));
    ASSERT_EQ(POWER_SUSPEND_NONE, power_state_current_suspend_reason(&state));
    ASSERT_EQ(POWER_SUSPEND_USER, power_state_last_suspend_reason(&state));
    ASSERT_EQ(1, power_state_suspend_count(&state));
    ASSERT_EQ(1, power_state_resume_count(&state));

    return 0;
}

static int test_wake_sources_only_apply_while_suspended(void) {
    power_state_machine_t state;

    power_state_init(&state);
    ASSERT_FALSE(power_state_can_wake(&state, POWER_WAKE_BUTTON));

    ASSERT_TRUE(power_state_request_suspend(&state, POWER_SUSPEND_VIDEO_LOSS));
    ASSERT_FALSE(power_state_can_wake(&state, POWER_WAKE_BUTTON));

    power_state_mark_suspended(&state);
    ASSERT_FALSE(power_state_can_wake(&state, POWER_WAKE_NONE));
    ASSERT_TRUE(power_state_can_wake(&state, POWER_WAKE_BUTTON));
    ASSERT_TRUE(power_state_can_wake(&state, POWER_WAKE_USB_PD));
    ASSERT_TRUE(power_state_can_wake(&state, POWER_WAKE_USB));
    ASSERT_TRUE(power_state_can_wake(&state, POWER_WAKE_INPUT));

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_suspend_resume_transitions_are_ordered();
    rc |= test_wake_sources_only_apply_while_suspended();

    return rc;
}
