#include "wake_event_latch.h"

#include <stddef.h>

void wake_event_latch_arm(wake_event_latch_t *latch) {
    if (latch == NULL)
        return;
    latch->pending = false;
    latch->armed = true;
}

void wake_event_latch_disarm(wake_event_latch_t *latch) {
    if (latch == NULL)
        return;
    latch->armed = false;
    latch->pending = false;
}

void wake_event_latch_signal(wake_event_latch_t *latch) {
    if ((latch != NULL) && latch->armed)
        latch->pending = true;
}

bool wake_event_latch_take(wake_event_latch_t *latch) {
    if ((latch == NULL) || !latch->armed)
        return false;

    bool pending = latch->pending;
    latch->pending = false;
    return pending;
}
