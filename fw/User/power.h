//
// Grimoire
// Copyright 2025 Wenting Zhang
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
//
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "power_state.h"

// Requests posted from other contexts (USB HID callback, shell) and
// consumed by the UI task, which owns the suspend/resume flow.
typedef enum {
    POWER_REQ_NONE = 0,
    POWER_REQ_RETAIN,        // EPD rails off, image retained, auto-wake on video change
    POWER_REQ_RETAIN_NOWAKE, // As above, but only explicit resume/button wakes
    POWER_REQ_SUSPEND,       // Full device-level suspend
    POWER_REQ_RESUME,
} power_request_t;

typedef enum {
    // Rails with both voltage and current monitoring
    RAIL_5VES,
    RAIL_5VEG,
    RAIL_3V3,
    RAIL_1V8VID,
    RAIL_3V3VID,
    RAIL_5V2FL,
    RAIL_1V35,
    RAIL_1V2,
    // Rails with only voltage monitoring
    RAIL_VP,
    RAIL_VGH,
    RAIL_VBUS,
    RAIL_VCOM,
    RAIL_VN,
    RAIL_VGL,
} power_rail_t;

void power_off(void);
void power_suspend(power_suspend_reason_t reason);
void power_init(void);
power_state_t power_get_state(void);
power_suspend_reason_t power_get_current_suspend_reason(void);
power_suspend_reason_t power_get_last_suspend_reason(void);
bool power_is_suspended(void);
bool power_request_resume(uint32_t wake_sources);
void power_post_request(power_request_t req);
power_request_t power_take_request(void);
void power_retain_deepen(power_suspend_reason_t reason);
bool power_is_retained(void);
void power_resume_complete(void);
uint32_t power_get_last_wake_sources(void);
uint32_t power_get_suspend_count(void);
uint32_t power_get_resume_count(void);
void power_on(void);
void power_on_epd(void);
void power_off_epd(void);
void power_set_vcom(float vcom);
void power_set_vgh(float vgh);
void power_on_fl(void);
void power_off_fl(void);
void power_set_fl_brightness(uint8_t val);
float power_get_rail_voltage(power_rail_t rail);
float power_get_rail_current(power_rail_t rail);
void power_get_rail_power(power_rail_t rail, float *cur, float *avg, float *max);
portTASK_FUNCTION(power_monitor_task, pvParameters);
