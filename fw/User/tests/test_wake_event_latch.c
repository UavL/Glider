#include <stdbool.h>
#include <stdio.h>

#include "wake_event_latch.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_FALSE(expr) ASSERT_TRUE(!(expr))

static int test_disarmed_events_do_not_become_wakes(void) {
    wake_event_latch_t latch = {0};

    wake_event_latch_signal(&latch);
    ASSERT_FALSE(wake_event_latch_take(&latch));

    wake_event_latch_arm(&latch);
    ASSERT_FALSE(wake_event_latch_take(&latch));

    return 0;
}

static int test_arming_clears_stale_pending_event(void) {
    wake_event_latch_t latch = {0};

    wake_event_latch_arm(&latch);
    wake_event_latch_signal(&latch);
    wake_event_latch_disarm(&latch);
    wake_event_latch_arm(&latch);

    ASSERT_FALSE(wake_event_latch_take(&latch));

    return 0;
}

static int test_armed_events_are_one_shot(void) {
    wake_event_latch_t latch = {0};

    wake_event_latch_arm(&latch);
    wake_event_latch_signal(&latch);

    ASSERT_TRUE(wake_event_latch_take(&latch));
    ASSERT_FALSE(wake_event_latch_take(&latch));

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_disarmed_events_do_not_become_wakes();
    rc |= test_arming_clears_stale_pending_event();
    rc |= test_armed_events_are_one_shot();

    return rc;
}
