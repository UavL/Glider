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
#include "platform.h"
#include "board.h"
#include "app.h"
#include "numfmt.h"

static bool adc_conv_done;
static uint16_t adc_buffer[6];

static float voltages[14];
static float currents[8];
static float p_cur[8];
static float p_avg[8];
static float p_max[8];
static power_state_machine_t power_state;
static volatile power_request_t pending_request = POWER_REQ_NONE;

// Rail telemetry refresh period. power_on_epd() temporarily switches to
// fast sampling so rail bring-up is bounded by converter settling time
// instead of the telemetry period.
#define POWER_MONITOR_PERIOD_MS         100
#define POWER_MONITOR_FAST_PERIOD_MS    10
static volatile uint32_t monitor_period_ms = POWER_MONITOR_PERIOD_MS;

static void power_monitor_set_fast(bool fast) {
    monitor_period_ms = fast ?
            POWER_MONITOR_FAST_PERIOD_MS : POWER_MONITOR_PERIOD_MS;
}

#define ABSF(x) (((x) < 0) ? (0.f-(x)) : (x))

static void syslog_voltage(const char *name, float value) {
    char text[16];

    numfmt_format_fixed(text, sizeof(text), value, 2);
    syslog_printf("%s: %s V\n", name, text);
}

void power_on(void) {

}

void power_init(void) {
    power_state_init(&power_state);
}

void power_post_request(power_request_t req) {
    taskENTER_CRITICAL();
    pending_request = req;
    taskEXIT_CRITICAL();
}

power_request_t power_take_request(void) {
    power_request_t req;

    taskENTER_CRITICAL();
    req = pending_request;
    pending_request = POWER_REQ_NONE;
    taskEXIT_CRITICAL();
    return req;
}

bool power_is_retained(void) {
    return (power_get_state() == POWER_STATE_SUSPENDED) &&
            (power_get_current_suspend_reason() == POWER_SUSPEND_RETAIN);
}

power_state_t power_get_state(void) {
    return power_state_current(&power_state);
}

power_suspend_reason_t power_get_current_suspend_reason(void) {
    return power_state_current_suspend_reason(&power_state);
}

power_suspend_reason_t power_get_last_suspend_reason(void) {
    return power_state_last_suspend_reason(&power_state);
}

bool power_is_suspended(void) {
    return power_get_state() == POWER_STATE_SUSPENDED;
}

bool power_request_resume(uint32_t wake_sources) {
    return power_state_request_resume(&power_state, wake_sources);
}

void power_resume_complete(void) {
    power_state_mark_active(&power_state);
}

uint32_t power_get_last_wake_sources(void) {
    return power_state_last_wake_sources(&power_state);
}

uint32_t power_get_suspend_count(void) {
    return power_state_suspend_count(&power_state);
}

uint32_t power_get_resume_count(void) {
    return power_state_resume_count(&power_state);
}

void power_off(void) {
    power_suspend(POWER_SUSPEND_USER);
}

void power_suspend(power_suspend_reason_t reason) {
    if (!power_state_request_suspend(&power_state, reason))
        return;

    syslog_print("Suspending system");
    if (reason == POWER_SUSPEND_RETAIN) {
        // Light suspend: EPD rails off, last image retained on the panel.
        // FPGA, framebuffer and video frontends stay alive for fast resume.
        power_off_epd();
        gpio_put(LED_GRN, 0);
        gpio_put(LED_RED, 0);
        power_state_mark_suspended(&power_state);
        syslog_print("System in retain suspend");
        return;
    }
    if (reason != POWER_SUSPEND_VIDEO_LOSS) {
        usbpd_disarm_wake();
        usbpd_suspend_displayport();
    }
    power_off_epd();
    fpga_suspend();
    if (reason != POWER_SUSPEND_VIDEO_LOSS) {
        adv7611_powerdown();
        ptn3460_powerdown();
        gpio_put(HPD_EN, 0);
        gpio_put(DEC_RST, 0);
        gpio_put(DP_PDN, 0);
    }
    gpio_put(LED_GRN, 0);
    gpio_put(LED_RED, 0);

    power_state_mark_suspended(&power_state);
    if (reason != POWER_SUSPEND_VIDEO_LOSS)
        usbpd_disarm_wake();
    syslog_print("System suspended");
}

// Escalate an active retain suspend to a deeper suspend reason, applying the
// shutdown steps that retain skipped. Used when video or the USB bus goes
// away while the display is in the retain state.
void power_retain_deepen(power_suspend_reason_t reason) {
    if (!power_is_retained())
        return;

    syslog_printf("Deepening retain suspend, reason %d\n", (int)reason);
    if (reason != POWER_SUSPEND_VIDEO_LOSS) {
        usbpd_disarm_wake();
        usbpd_suspend_displayport();
    }
    fpga_suspend();
    if (reason != POWER_SUSPEND_VIDEO_LOSS) {
        adv7611_powerdown();
        ptn3460_powerdown();
        gpio_put(HPD_EN, 0);
        gpio_put(DEC_RST, 0);
        gpio_put(DP_PDN, 0);
    }
    power_state_update_suspend_reason(&power_state, reason);
}

#define EPD_PWRUP_POLL_MS       10
#define EPD_PWRUP_TIMEOUT_MS    1200

static bool epd_neg_rails_good(void) {
    float vn = power_get_rail_voltage(RAIL_VN);
    float vgl = power_get_rail_voltage(RAIL_VGL);
    return (vn <= -14.0f) && (vn >= -16.0f) &&
            (vgl <= -19.0f) && (vgl >= -21.0f);
}

static bool epd_pos_rails_good(void) {
    float vp = power_get_rail_voltage(RAIL_VP);
    float vgh = power_get_rail_voltage(RAIL_VGH);
    return (vp >= 14.0f) && (vp <= 16.0f) &&
            (vgh >= 21.0f) && (vgh <= 28.0f);
}

static bool epd_vcom_good(void) {
    float v = power_get_rail_voltage(RAIL_VCOM);
    return ABSF(v - config.vcom) < 0.2f; // Allow up to 0.2V difference
}

static bool epd_wait_rails(bool (*good)(void)) {
    uint32_t waited = 0;

    while (!good()) {
        if (waited >= EPD_PWRUP_TIMEOUT_MS)
            return false;
        sleep_ms(EPD_PWRUP_POLL_MS);
        waited += EPD_PWRUP_POLL_MS;
    }
    return true;
}

void power_on_epd(void) {
    power_monitor_set_fast(true);
    gpio_put(VCOM_MEN, 1); // Disable
    gpio_put(VCOM_EN, 1); // Disable
    HAL_DAC_Start(&hdac1, DAC_CHANNEL_1);
    gpio_put(EPD_PWREN, 1);
    if (!epd_wait_rails(epd_neg_rails_good)) {
        syslog_voltage("VN", power_get_rail_voltage(RAIL_VN));
        syslog_voltage("VGL", power_get_rail_voltage(RAIL_VGL));
        power_monitor_set_fast(false);
        fatal("Failed to bring up neg rails");
    }
    syslog_voltage("VN", power_get_rail_voltage(RAIL_VN));
    syslog_voltage("VGL", power_get_rail_voltage(RAIL_VGL));
    gpio_put(EPD_POSEN, 1);
    HAL_DAC_Start(&hdac1, DAC_CHANNEL_2);
    if (!epd_wait_rails(epd_pos_rails_good)) {
        syslog_voltage("VP", power_get_rail_voltage(RAIL_VP));
        syslog_voltage("VGH", power_get_rail_voltage(RAIL_VGH));
        power_monitor_set_fast(false);
        fatal("Failed to bring up pos rails");
    }
    syslog_voltage("VP", power_get_rail_voltage(RAIL_VP));
    syslog_voltage("VGH", power_get_rail_voltage(RAIL_VGH));
    gpio_put(VCOM_EN, 0); // Enable
    gpio_put(VCOM_MEN, 0); // Enable
    if (!epd_wait_rails(epd_vcom_good)) {
        syslog_voltage("VCOM", power_get_rail_voltage(RAIL_VCOM));
        power_monitor_set_fast(false);
        fatal("Failed to bring up VCOM");
    }
    syslog_voltage("VCOM", power_get_rail_voltage(RAIL_VCOM));
    power_monitor_set_fast(false);
}

void power_off_epd(void) {
    gpio_put(VCOM_EN, 1); // Disable
    gpio_put(VCOM_MEN, 1); // Disable
	sleep_ms(10);
	gpio_put(EPD_POSEN, 0);
	HAL_DAC_Stop(&hdac1, DAC_CHANNEL_2);
	sleep_ms(10);
    gpio_put(EPD_PWREN, 0);
    HAL_DAC_Stop(&hdac1, DAC_CHANNEL_1);
}

void power_set_vcom(float vcom) {
    // DAC 000 = -2.667V
    // DAC 19A = -2.404V
    // DAC E80 = -0.226V
    // DAC FF0 = -0.011V
    // V = 0.000651 * set - 2.667
    // set = (V + 2.676) / 0.000651
    float setpt = (vcom + 2.676f) / 0.00066f;
    int setpt_i = (int)roundf(setpt);
    if (setpt_i < 0)
        setpt_i = 0;
    if (setpt_i > 4095)
        setpt_i = 4095;

    HAL_DAC_SetValue(&hdac1, DAC_CHANNEL_1, DAC_ALIGN_12B_R, setpt_i);
}

void power_set_vgh(float vgh) {
    // DAC 000 26.87V
    // DAC 0F2 26.19V
    // DAC 77E 20.95V
    // DAC FF0 12.26V
	// Valid range: 22V - 27V
    // set = (26.945 - V) / 0.03126
    float setpt = (26.945f - vgh) / 0.003126f;
    int setpt_i = (int)roundf(setpt);
    if (setpt_i < 0)
        setpt_i = 0;
    if (setpt_i > 4095)
        setpt_i = 4095;

    HAL_DAC_SetValue(&hdac1, DAC_CHANNEL_2, DAC_ALIGN_12B_R, setpt_i);
}

void power_on_fl(void) {
	//HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
}

void power_off_fl(void) {
	//HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_3);
}

void power_set_fl_brightness(uint8_t val) {
	//TIM1->CCR3 = 255 - val;
}

static void ina_write(uint8_t addr, uint8_t reg, uint16_t val) {
    uint8_t buf[2] = {val & 0xff, val >> 8};
    int result = pal_i2c_write_longreg(INA3221_I2C, addr, reg, buf, 2);
    if (result != 0) {
        syslog_printf("Failed writing data to INA3221\n");
    }
}

static uint16_t ina_read(uint8_t addr, uint8_t reg) {
    uint8_t buf[2];
    int result = pal_i2c_read_payload(INA3221_I2C, addr, &reg, 1, buf, 2);
    if (result != 0) {
        syslog_printf("Failed reading data from INA3221\n");
    }
    return ((uint16_t)buf[0] << 8) | buf[1];
}

static void power_ina_init(uint8_t addr) {
    syslog_printf("INA %02x: Mfg ID = %04x, Die ID = %04x\n", addr, ina_read(addr, 0xfe), ina_read(addr, 0xff));
}

float power_get_rail_voltage(power_rail_t rail) {
    return voltages[(int)rail];
}

float power_get_rail_current(power_rail_t rail) {
    int ch = (int)rail;
    if (ch > 8)
        return 0.0f;
    return currents[ch];
}

void power_get_rail_power(power_rail_t rail, float *cur, float *avg, float *max) {
    *cur = p_cur[(int)rail];
    *avg = p_avg[(int)rail];
    *max = p_max[(int)rail];
}

// No internal reference, ref_voltage is the full level (65535) voltage / VDDA voltage
static float convert_positive_adc_voltage(uint16_t sample, float ref_voltage) {
    return (float)sample / 65535.0f * ref_voltage * 11.0f;
}

static float convert_negative_adc_voltage(uint16_t sample, float ref_voltage) {
    return convert_positive_adc_voltage(sample, ref_voltage) - ref_voltage * 10.f;
}

static float convert_vcom_adc_voltage(uint16_t sample, float ref_voltage) {
    return (float)sample / 65535.0f * ref_voltage * 3.18f - ref_voltage * 2.18f;
}

static float convert_bus_voltage(uint16_t sample) {
    return (float)(*(int16_t *)&sample) / 1000.f;
}

static float convert_shunt_current(uint16_t sample) {
    float shunt_mv = (float)(*(int16_t *)&sample) / 200.f;
    float shunt_ma = shunt_mv / 0.02f;
    return shunt_ma;
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc) {
    adc_conv_done = true;
    HAL_ADC_Stop_DMA(hadc);
}

portTASK_FUNCTION(power_monitor_task, pvParameters) {
    HAL_StatusTypeDef result = HAL_ADCEx_Calibration_Start(&hadc1, ADC_CALIB_OFFSET_LINEARITY, ADC_SINGLE_ENDED);
    if (result != HAL_OK) {
        syslog_printf("ADC failed to calibrate\n");
    }
    power_ina_init(INA3221_0_I2C_ADDR);
    power_ina_init(INA3221_1_I2C_ADDR);
    power_ina_init(INA3221_2_I2C_ADDR);
    adc_conv_done = true;
    const uint8_t ina_shunt_regs[] = {
        // I2C ADDR, REG NUM
        INA3221_0_I2C_ADDR, 0x01,
        INA3221_0_I2C_ADDR, 0x03,
        INA3221_0_I2C_ADDR, 0x05,
        INA3221_1_I2C_ADDR, 0x01,
        INA3221_1_I2C_ADDR, 0x03,
        INA3221_1_I2C_ADDR, 0x05,
        INA3221_2_I2C_ADDR, 0x01,
        INA3221_2_I2C_ADDR, 0x03,
    };
    const uint8_t ina_bus_regs[] = {
        // I2C ADDR, REG NUM
        INA3221_0_I2C_ADDR, 0x02,
        INA3221_0_I2C_ADDR, 0x04,
        INA3221_0_I2C_ADDR, 0x06,
        INA3221_1_I2C_ADDR, 0x02,
        INA3221_1_I2C_ADDR, 0x04,
        INA3221_1_I2C_ADDR, 0x06,
        INA3221_2_I2C_ADDR, 0x02,
        INA3221_2_I2C_ADDR, 0x04,
    };
    while (1) {
        for (int i = 0; i < 8; i++) {
            currents[i] = convert_shunt_current(ina_read(ina_shunt_regs[i * 2], ina_shunt_regs[i * 2 + 1]));
            voltages[i] = convert_bus_voltage(ina_read(ina_bus_regs[i * 2], ina_bus_regs[i * 2 + 1]));
        }
        if (adc_conv_done == true) {
            // Update numbers
            for (int i = 0; i < 3; i++) {
                voltages[8 + i] = convert_positive_adc_voltage(adc_buffer[i], voltages[RAIL_3V3]);
            }
            for (int i = 3; i < 6; i++) {
                voltages[8 + i] = convert_negative_adc_voltage(adc_buffer[i], voltages[RAIL_3V3]);
            }
            voltages[(int)RAIL_VCOM] = convert_vcom_adc_voltage(adc_buffer[3], voltages[RAIL_3V3]);
            adc_conv_done = false;
            HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_buffer, 6);
        }
        // Update values
        for (int i = 0; i < 8; i++) {
            p_cur[i] = voltages[i] * currents[i];
            p_avg[i] = p_avg[i] * 0.9f + p_cur[i] * 0.1f;
            if (p_cur[i] > p_max[i]) p_max[i] = p_cur[i];
        }
        vTaskDelay(pdMS_TO_TICKS(monitor_period_ms));
    }
}
