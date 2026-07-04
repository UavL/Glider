#pragma once

#include <stdbool.h>
#include <stdint.h>

uint32_t autoclear_scaled_threshold(int threshold, uint16_t hact, uint16_t vact);
bool autoclear_adaptive_update(uint32_t *accumulated_damage,
        uint32_t *last_damage, uint32_t current_damage, int threshold,
        uint16_t hact, uint16_t vact);
uint32_t autoclear_fixed_interval_ms(int interval);
int autoclear_toggle_mode(int current_mode, int *previous_mode);
void autoclear_reset(uint32_t *accumulated_damage, uint32_t *last_damage);
