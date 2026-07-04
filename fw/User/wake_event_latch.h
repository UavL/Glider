#pragma once

#include <stdbool.h>

typedef struct {
    volatile bool armed;
    volatile bool pending;
} wake_event_latch_t;

void wake_event_latch_arm(wake_event_latch_t *latch);
void wake_event_latch_disarm(wake_event_latch_t *latch);
void wake_event_latch_signal(wake_event_latch_t *latch);
bool wake_event_latch_take(wake_event_latch_t *latch);
