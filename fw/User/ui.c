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
#include <stdio.h>
#include <string.h>
#include "ui.h"
#include "osd_font.h"
#include "ui_menu.h"

static QueueHandle_t btn_queue;

typedef enum {
    BTN1_SHORT_PRESSED,
    BTN1_LONG_PRESSED,
    BTN2_SHORT_PRESSED,
    BTN2_LONG_PRESSED,
    BTN3_SHORT_PRESSED,
    BTN3_LONG_PRESSED
} btn_event_t;

static int mode = 0;

typedef struct {
    update_mode_t id;
    char *name;
} update_mode_item_t;

const update_mode_item_t modes[] = {
    {UM_FAST_MONO_BAYER, "Browsing"},
    {UM_FAST_MONO_BLUE_NOISE, "Watching"},
    {UM_FAST_GREY, "Typing"},
    {UM_AUTO_LUT_NO_DITHER, "Reading"},
};

static int mode_max = sizeof(modes) / sizeof(modes[0]);

#define OSD_WIDTH   CASTER_OSD_WIDTH
#define OSD_HEIGHT  CASTER_OSD_HEIGHT
#define OSD_BLACK   false
#define OSD_WHITE   true
static uint8_t osd_fb[CASTER_OSD_BUF_SIZE];

typedef struct {
    const osd_font_t *small;
    const osd_font_t *item;
    const osd_font_t *large;
} osd_fonts_t;

typedef struct {
    int first_row;
    int category_index;
    ui_menu_depth_t depth;
} osd_menu_render_state_t;

void ui_init(void) {
    btn_queue = xQueueCreate(8, sizeof(btn_event_t));
}

static void osd_set_pixel(int x, int y, bool p) {
    if (x >= OSD_WIDTH)
        return;
    if (y >= OSD_HEIGHT)
        return;
    if (x < 0)
        return;
    if (y < 0)
        return;
    int x_byte = x / 8;
    int x_bit = x % 8;
    if (p)
        osd_fb[y * OSD_WIDTH / 8 + x_byte] |= (0x80 >> x_bit);
    else
        osd_fb[y * OSD_WIDTH / 8 + x_byte] &= ~(0x80 >> x_bit);
}

static void osd_clear(uint8_t c) {
    memset(osd_fb, c, OSD_WIDTH * OSD_HEIGHT / 8);
}

static void osd_fill_rect(int x, int y, int w, int h, bool color) {
    for (int yy = y; yy < y + h; yy++) {
        for (int xx = x; xx < x + w; xx++) {
            osd_set_pixel(xx, yy, color);
        }
    }
}

static void osd_draw_rect(int x, int y, int w, int h, bool color, int thickness) {
    for (int i = 0; i < thickness; i++) {
        osd_fill_rect(x + i, y + i, w - i * 2, 1, color);
        osd_fill_rect(x + i, y + h - 1 - i, w - i * 2, 1, color);
        osd_fill_rect(x + i, y + i, 1, h - i * 2, color);
        osd_fill_rect(x + w - 1 - i, y + i, 1, h - i * 2, color);
    }
}

static const osd_font_t *load_osd_font(const char *fn) {
    SPIFFS_clearerr(&spiffs_fs);
    spiffs_file f = SPIFFS_open(&spiffs_fs, fn, SPIFFS_O_RDONLY, 0);
    if (SPIFFS_errno(&spiffs_fs) != 0)
        return NULL;

    spiffs_stat s;
    SPIFFS_fstat(&spiffs_fs, f, &s);
    uint32_t size = s.size;

    uint8_t *buf = pvPortMalloc(size);
    if (!buf) {
        SPIFFS_close(&spiffs_fs, f);
        return NULL;
    }

    SPIFFS_read(&spiffs_fs, f, buf, size);
    SPIFFS_close(&spiffs_fs, f);

    const osd_font_t *font = osd_font_from_memory(buf, size);
    if (font == NULL) {
        vPortFree(buf);
        return NULL;
    }

    return font;
}

static int osd_draw_prop_char(const osd_font_t *font, int x, int y, uint32_t chr,
        bool color, int max_width) {
    if ((font == NULL) || (max_width <= 0))
        return 0;

    const osd_font_glyph_t *glyph = osd_font_get_glyph(font, chr);
    if (glyph == NULL)
        return 0;

    uint32_t row_words = (font->header.glyph_words - 1) / font->header.height;
    uint32_t draw_width = glyph->width;
    if ((int)draw_width > max_width)
        draw_width = max_width;

    for (uint32_t yy = 0; yy < font->header.height; yy++) {
        const uint32_t *row = glyph->rows + yy * row_words;
        for (uint32_t xx = 0; xx < draw_width; xx++) {
            if (row[xx / 32] & (0x80000000u >> (xx % 32)))
                osd_set_pixel(x + xx, y + yy, color);
        }
    }

    return glyph->width;
}

static void osd_draw_prop_string(const osd_font_t *font, int x, int y, const char *string,
        int max_width, bool color) {
    int xx = x;
    while ((string != NULL) && (*string != '\0') && (xx < x + max_width)) {
        int used = osd_draw_prop_char(font, xx, y, (uint8_t)*string, color,
                x + max_width - xx);
        if (used <= 0)
            used = 4;
        xx += used;
        string++;
    }
}

static void osd_draw_right_string(const osd_font_t *font, int right, int y,
        const char *string, int max_width, bool color) {
    int width = osd_font_text_width(font, string, 64);
    if (width > max_width)
        width = max_width;
    osd_draw_prop_string(font, right - width, y, string, max_width, color);
}

static const osd_font_t *font_or(const osd_font_t *preferred, const osd_font_t *fallback) {
    return preferred ? preferred : fallback;
}

static int mode_index_for(update_mode_t id) {
    for (int i = 0; i < mode_max; i++) {
        if (modes[i].id == id)
            return i;
    }
    return 0;
}

static void draw_status_popup(const osd_fonts_t *fonts, const char *title, const char *value) {
    osd_clear(0xff);
    osd_draw_prop_string(font_or(fonts->item, fonts->large), 12, 20, title,
            OSD_WIDTH - 24, OSD_BLACK);
    osd_draw_prop_string(font_or(fonts->large, fonts->item), 12, 72, value,
            OSD_WIDTH - 24, OSD_BLACK);
    caster_osd_send_buf(osd_fb);
    caster_osd_set_enable(true);
}

static void menu_render_state_reset(osd_menu_render_state_t *state, const ui_menu_t *menu) {
    state->first_row = 0;
    state->category_index = menu->category_index;
    state->depth = ui_menu_depth(menu);
}

static void draw_menu_row(const osd_fonts_t *fonts, int y, int h, bool selected,
        const char *label, const char *value) {
    bool fg = selected ? OSD_WHITE : OSD_BLACK;
    bool bg = selected ? OSD_BLACK : OSD_WHITE;
    int x = 8;
    int w = OSD_WIDTH - 16;

    osd_fill_rect(x, y, w, h, bg);
    osd_draw_rect(x, y, w, h, OSD_BLACK, selected ? 2 : 1);

    const osd_font_t *item_font = font_or(fonts->item, fonts->small);
    const osd_font_t *value_font = font_or(fonts->small, fonts->item);
    int text_y = y + ((h > 34) ? 9 : 6);
    if (value != NULL && value[0] != '\0') {
        osd_draw_prop_string(item_font, x + 8, text_y, label, w - 110, fg);
        osd_draw_right_string(value_font, x + w - 8, text_y + 2, value, 96, fg);
    }
    else {
        osd_draw_prop_string(item_font, x + 8, text_y, label, w - 16, fg);
    }
}

static void draw_slider_modal(const osd_fonts_t *fonts, const ui_menu_t *menu) {
    int x = 8;
    int y = 34;
    int w = OSD_WIDTH - 16;
    int h = OSD_HEIGHT - y - 22 - 4;
    int rail_x = x + 24;
    int rail_w = w - 48;
    int rail_y = y + 118;
    int count = ui_menu_modal_count(menu);
    int index = ui_menu_modal_index(menu);
    int tick_step = (count > 1) ? rail_w / (count - 1) : 0;
    int knob_x = rail_x + tick_step * index;

    osd_fill_rect(x, y, w, h, OSD_WHITE);
    osd_draw_rect(x, y, w, h, OSD_BLACK, 3);

    osd_draw_prop_string(font_or(fonts->item, fonts->small), x + 8, y + 10,
            ui_menu_selected_label(menu), w - 16, OSD_BLACK);
    osd_draw_prop_string(font_or(fonts->large, fonts->item), x + 12, y + 62,
            ui_menu_modal_value_label(menu), w - 24, OSD_BLACK);

    osd_fill_rect(rail_x, rail_y - 2, rail_w, 4, OSD_BLACK);
    for (int i = 0; i < count; i++) {
        int tx = rail_x + tick_step * i;
        osd_fill_rect(tx - 1, rail_y - 7, 2, 14, OSD_BLACK);
    }
    osd_fill_rect(knob_x - 6, rail_y - 10, 12, 20, OSD_BLACK);

    osd_draw_prop_string(font_or(fonts->small, fonts->item), rail_x, rail_y + 18,
            "-3", 36, OSD_BLACK);
    osd_draw_right_string(font_or(fonts->small, fonts->item), rail_x + rail_w,
            rail_y + 18, "3", 36, OSD_BLACK);
}

static void draw_list_modal(const osd_fonts_t *fonts, const ui_menu_t *menu,
        int first, int visible) {
    int x = 8;
    int y = 34;
    int w = OSD_WIDTH - 16;
    int h = OSD_HEIGHT - y - 22 - 4;
    int row_top = y + 30;
    int row_h = 26;
    int count = ui_menu_row_count(menu);

    osd_fill_rect(x, y, w, h, OSD_WHITE);
    osd_draw_rect(x, y, w, h, OSD_BLACK, 3);

    osd_draw_prop_string(font_or(fonts->item, fonts->small), x + 8, y + 10,
            ui_menu_selected_label(menu), w - 16, OSD_BLACK);

    if (visible > (h - 34) / row_h)
        visible = (h - 34) / row_h;
    if (visible < 1)
        visible = 1;

    for (int row = first; (row < count) && (row < first + visible); row++) {
        bool selected = ui_menu_row_selected(menu, row);
        bool fg = selected ? OSD_WHITE : OSD_BLACK;
        bool bg = selected ? OSD_BLACK : OSD_WHITE;
        int yy = row_top + (row - first) * row_h;
        osd_fill_rect(x + 8, yy, w - 16, row_h - 3, bg);
        osd_draw_prop_string(font_or(fonts->small, fonts->item), x + 11, yy + 4,
                ui_menu_row_label(menu, row), w - 22, fg);
    }
}

static int menu_selected_row(const ui_menu_t *menu) {
    int rows = ui_menu_row_count(menu);
    for (int i = 0; i < rows; i++) {
        if (ui_menu_row_selected(menu, i))
            return i;
    }
    return 0;
}

static void render_settings_menu(const osd_fonts_t *fonts, const ui_menu_t *menu,
        osd_menu_render_state_t *render_state) {
    osd_clear(0xff);

    if ((render_state->category_index != menu->category_index) ||
            (render_state->depth != ui_menu_depth(menu))) {
        menu_render_state_reset(render_state, menu);
    }

    osd_fill_rect(0, 0, OSD_WIDTH, 28, OSD_BLACK);
    osd_draw_prop_string(font_or(fonts->item, fonts->small), 8, 5, "Settings",
            90, OSD_WHITE);
    osd_draw_prop_string(font_or(fonts->small, fonts->item), 110, 8,
            (ui_menu_depth(menu) == UI_MENU_DEPTH_CATEGORIES) ? "Top Level" :
            ui_menu_category_label(menu), OSD_WIDTH - 118, OSD_WHITE);

    int top = 34;
    int bottom = OSD_HEIGHT - 22;
    int row_h = (ui_menu_depth(menu) == UI_MENU_DEPTH_CATEGORIES) ? 46 : 36;
    int visible = (bottom - top) / row_h;
    int count = ui_menu_row_count(menu);
    int selected = menu_selected_row(menu);
    int viewport_visible = visible;
    if ((ui_menu_depth(menu) == UI_MENU_DEPTH_MODAL) && !ui_menu_modal_is_scalar(menu))
        viewport_visible = (OSD_HEIGHT - 34 - 22 - 4 - 34) / 26;
    int first = ui_menu_viewport_first(render_state->first_row, selected, count, viewport_visible);
    render_state->first_row = first;

    if (visible < 1)
        visible = 1;
    if (viewport_visible < 1)
        viewport_visible = 1;

    if (ui_menu_depth(menu) == UI_MENU_DEPTH_MODAL) {
        if (ui_menu_modal_is_scalar(menu))
            draw_slider_modal(fonts, menu);
        else
            draw_list_modal(fonts, menu, first, viewport_visible);
    }
    else {
        for (int row = first; (row < count) && (row < first + visible); row++) {
            draw_menu_row(fonts, top + (row - first) * row_h, row_h - 4,
                ui_menu_row_selected(menu, row),
                ui_menu_row_label(menu, row),
                ui_menu_row_value(menu, row));
        }
    }

    osd_draw_rect(0, OSD_HEIGHT - 20, OSD_WIDTH, 20, OSD_BLACK, 1);
    const char *hint;
    if ((ui_menu_depth(menu) == UI_MENU_DEPTH_MODAL) && ui_menu_modal_is_scalar(menu))
        hint = "B1/B2 Adj  B3 OK  L3 Back";
    else if (ui_menu_depth(menu) == UI_MENU_DEPTH_MODAL)
        hint = "B1/B2 Up/Dn  B3 OK  L3 Back";
    else
        hint = "B1/B2 Up/Dn  B3 Ent  L3 Back";
    osd_draw_prop_string(font_or(fonts->small, fonts->item), 5, OSD_HEIGHT - 18,
            hint, OSD_WIDTH - 48, OSD_BLACK);

    char page[12];
    snprintf(page, sizeof(page), "%d/%d", selected + 1, count);
    osd_draw_right_string(font_or(fonts->small, fonts->item), OSD_WIDTH - 5,
            OSD_HEIGHT - 18, page, 42, OSD_BLACK);

    caster_osd_send_buf(osd_fb);
    caster_osd_set_enable(true);
}

static uint32_t autoclear_interval_ms(void) {
    switch (config.autoclear_interval) {
    case AC_1MIN:
        return 60000;
    case AC_15MIN:
        return 15 * 60000;
    case AC_5MIN:
    default:
        return 5 * 60000;
    }
}

static int binding_index_for_event(btn_event_t event) {
    switch (event) {
    case BTN1_SHORT_PRESSED:
        return 0;
    case BTN2_SHORT_PRESSED:
        return 1;
    case BTN3_SHORT_PRESSED:
        return 2;
    case BTN1_LONG_PRESSED:
        return 3;
    case BTN2_LONG_PRESSED:
        return 4;
    case BTN3_LONG_PRESSED:
        return 5;
    default:
        return -1;
    }
}

static const char *input_label(uint8_t input) {
    switch (input) {
    case INPUT_SEL_TMDS:
        return "TMDS";
    case INPUT_SEL_DP:
        return "DP";
    case INPUT_SEL_AUTO:
    default:
        return "Auto";
    }
}

static void apply_display_mode(update_mode_t id, const osd_fonts_t *fonts,
        TickType_t *osd_timeout) {
    mode = mode_index_for(id);
    config.update_mode = modes[mode].id;
    caster_setmode(0, 0, config.hact, config.vact, modes[mode].id);
    config_save();

    draw_status_popup(fonts, "Mode", modes[mode].name);
    *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
}

static bool menu_config_changed(const config_t *previous) {
    return (previous->input_sel != config.input_sel) ||
            (previous->update_mode != config.update_mode) ||
            (previous->lightness != config.lightness) ||
            (previous->contrast != config.contrast) ||
            (previous->saturation != config.saturation) ||
            (previous->autoclear_mode != config.autoclear_mode) ||
            (previous->autoclear_interval != config.autoclear_interval) ||
            (previous->autoclear_threshold != config.autoclear_threshold) ||
            (memcmp(previous->button_actions, config.button_actions,
                    sizeof(config.button_actions)) != 0);
}

static void execute_button_action(button_action_t action, const osd_fonts_t *fonts,
        ui_menu_t *menu, bool *menu_open, bool *autoclear,
        TickType_t *osd_timeout, TickType_t *autoclear_timeout,
        osd_menu_render_state_t *render_state) {
    switch (action) {
    case ACT_PREV_MODE:
        mode--;
        if (mode < 0)
            mode = mode_max - 1;
        apply_display_mode(modes[mode].id, fonts, osd_timeout);
        break;
    case ACT_NEXT_MODE:
        mode++;
        if (mode >= mode_max)
            mode = 0;
        apply_display_mode(modes[mode].id, fonts, osd_timeout);
        break;
    case ACT_MODE_BROWSING:
        apply_display_mode(UM_FAST_MONO_BAYER, fonts, osd_timeout);
        break;
    case ACT_MODE_WATCHING:
        apply_display_mode(UM_FAST_MONO_BLUE_NOISE, fonts, osd_timeout);
        break;
    case ACT_MODE_TYPING:
        apply_display_mode(UM_FAST_GREY, fonts, osd_timeout);
        break;
    case ACT_MODE_READING:
        apply_display_mode(UM_AUTO_LUT_NO_DITHER, fonts, osd_timeout);
        break;
    case ACT_CLEAR:
        caster_redraw(0, 0, config.hact, config.vact);
        break;
    case ACT_TOGGLE_AC:
        config.autoclear_mode = *autoclear ? AC_OFF : AC_FIXED;
        *autoclear = config.autoclear_mode != AC_OFF;
        *autoclear_timeout = 0;
        config_save();
        draw_status_popup(fonts, "Auto Clear", *autoclear ? "ON" : "OFF");
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    case ACT_OPEN_SETTINGS:
        ui_menu_init(menu, &config);
        menu_render_state_reset(render_state, menu);
        *menu_open = true;
        *osd_timeout = 0;
        render_settings_menu(fonts, menu, render_state);
        break;
    case ACT_POFF:
        draw_status_popup(fonts, "Power", "Off");
        caster_redraw_blank();
        sleep_ms(200);
        caster_redraw(0, 0, config.hact, config.vact);
        sleep_ms(600);
        power_off();
        break;
    case ACT_INPUT_AUTO:
        config.input_sel = INPUT_SEL_AUTO;
        config_save();
        draw_status_popup(fonts, "Input", input_label(config.input_sel));
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    case ACT_INPUT_TMDS:
        config.input_sel = INPUT_SEL_TMDS;
        config_save();
        draw_status_popup(fonts, "Input", input_label(config.input_sel));
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    case ACT_INPUT_DP:
        config.input_sel = INPUT_SEL_DP;
        config_save();
        draw_status_popup(fonts, "Input", input_label(config.input_sel));
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    default:
        break;
    }
}

static bool is_tmds_active(void) {
    uint8_t val;
    val = adv7611_read_reg(HDMI_I2C_ADDR, 0x04);
    return !!(val & 0x2);
}

static bool is_dp_active(void) {
    return dp_ready;
}

static void restart_fpga(void) {
    fpga_init(config.bitstream);
    syslog_printf("Waiting for video signal to lock");
    while (true) {
        // Wait for PLL to lock
        vTaskDelay(pdMS_TO_TICKS(100));
        uint8_t result = fpga_write_reg8(CSR_ID0, 0x00);
        if (result == 0x35) {
            break;
        }
    }
    syslog_printf("FPGA up");
}

portTASK_FUNCTION(ui_task, pvParameters) {
    TickType_t osd_timeout = 0;
    TickType_t autoclear_timeout = 0;
    bool autoclear = config.autoclear_mode != AC_OFF;
    bool menu_open = false;
    ui_menu_t menu;
    osd_menu_render_state_t menu_render_state = {0};

    osd_fonts_t fonts = {
        .small = load_osd_font("fonts/font_quicksand_16.bin"),
        .item = load_osd_font("fonts/font_quicksand_20.bin"),
        .large = load_osd_font("fonts/font_quicksand_28.bin"),
    };

    mode = mode_index_for((update_mode_t)config.update_mode);

    // First wait link establish
    bool tmds_mode = false;

    if (config.input_sel == INPUT_SEL_DP) {
        tmds_mode = false;
        syslog_print("Forced to use DP input");
    }
    else if (config.input_sel == INPUT_SEL_TMDS) {
        tmds_mode = true;
        syslog_print("Forced to use TMDS input");
    }
    else {
        while (1) {
            // Check is DP on
            if (is_tmds_active()) {
                tmds_mode = true;
                break;
            }
            else if (is_dp_active()) {
                tmds_mode = false;
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(100)); // Wait before next iteration
        }
    }

    if (tmds_mode) {
        // Making sure video is active
        while (!is_tmds_active()) {
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        ptn3460_powerdown();
    }
    else {
        while (!is_dp_active()) {
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        adv7611_powerdown();
    }

    restart_fpga();
    power_on_epd();
    caster_init(); // Start refresh
    syslog_printf("FPGA started with status %02x", fpga_write_reg8(CSR_STATUS, 0x00));

    while (1) {
        // Check OSD timeout
        if ((osd_timeout != 0) && (((int32_t)xTaskGetTickCount() - (int32_t)osd_timeout) >= 0)) {
            osd_timeout = 0;
            caster_osd_set_enable(false);
        }

        // Update auto clear
        if ((autoclear_timeout != 0) && (((int32_t)xTaskGetTickCount() - (int32_t)autoclear_timeout) >= 0)) {
            caster_redraw(0, 0, config.hact, config.vact);
            autoclear_timeout = 0; // Pending reset
        }

        if (autoclear && (autoclear_timeout == 0)) {
            autoclear_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(autoclear_interval_ms());
        }

        if (!autoclear) {
            autoclear_timeout = 0;
        }

        // Detect loss of signal / lost access to FPGA
        if ((tmds_mode && (!is_tmds_active())) || (fpga_write_reg8(CSR_ID0, 0x00) != 0x35)) {
            // Stop and restart
            syslog_print("System reset!");
            power_off_epd();
            NVIC_SystemReset();
        }

        // Detect signal mode
        // TODO: This should be implemented in FPGA
#if 0
        if (tmds_mode) {
            uint16_t x, y;
            x = (uint16_t)(adv7611_read_reg(HDMI_I2C_ADDR, 0x07) & 0x1f) << 8;
            x |= adv7611_read_reg(HDMI_I2C_ADDR, 0x08);

            y = (uint16_t)(adv7611_read_reg(HDMI_I2C_ADDR, 0x09) & 0x1f) << 8;
            y |= adv7611_read_reg(HDMI_I2C_ADDR, 0x0a);

            if ((x != config.hact) || (y != config.vact)) {
                fatal("Incorrect input resolution, detected %d x %d.", x, y);
            }
        }
#endif

        // Key press logic
        btn_event_t btn_event;
        BaseType_t result = xQueueReceive(btn_queue, &btn_event, pdMS_TO_TICKS(200));
        if (result != pdTRUE)
            continue;

        if (menu_open) {
            config_t previous_config = config;
            update_mode_t previous_mode = (update_mode_t)config.update_mode;
            ui_menu_event_t menu_event = UI_MENU_EVENT_ENTER;
            bool close_menu = false;

            if (btn_event == BTN1_SHORT_PRESSED)
                menu_event = UI_MENU_EVENT_PREV;
            else if (btn_event == BTN2_SHORT_PRESSED)
                menu_event = UI_MENU_EVENT_NEXT;
            else if (btn_event == BTN3_SHORT_PRESSED)
                menu_event = UI_MENU_EVENT_ENTER;
            else if (btn_event == BTN3_LONG_PRESSED) {
                if (ui_menu_depth(&menu) == UI_MENU_DEPTH_CATEGORIES)
                    close_menu = true;
                else
                    menu_event = UI_MENU_EVENT_BACK;
            }
            else {
                render_settings_menu(&fonts, &menu, &menu_render_state);
                continue;
            }

            if (close_menu) {
                menu_open = false;
                caster_osd_set_enable(false);
            }
            else {
                ui_menu_handle(&menu, menu_event);
                if (menu_config_changed(&previous_config)) {
                    config_save();
                    autoclear = config.autoclear_mode != AC_OFF;
                    if (previous_config.autoclear_interval != config.autoclear_interval)
                        autoclear_timeout = 0;
                    if (previous_mode != (update_mode_t)config.update_mode) {
                        mode = mode_index_for((update_mode_t)config.update_mode);
                        caster_setmode(0, 0, config.hact, config.vact,
                                modes[mode].id);
                    }
                }
                render_settings_menu(&fonts, &menu, &menu_render_state);
            }
            osd_timeout = 0;
            continue;
        }

        int binding = binding_index_for_event(btn_event);
        if ((binding >= 0) && (binding < CONFIG_BUTTON_BINDING_COUNT)) {
            execute_button_action((button_action_t)config.button_actions[binding],
                    &fonts, &menu, &menu_open, &autoclear, &osd_timeout,
                    &autoclear_timeout, &menu_render_state);
        }
    }
}

portTASK_FUNCTION(key_scan_task, pvParameters) {
    while (1) {
        uint32_t scan = button_scan();
        btn_event_t event;
        // No wait, if the ui task doesn't take it, the key press is lost
        if ((scan & BTN_MASK) == BTN_SHORT_PRESSED) {
            event = BTN3_SHORT_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        else if ((scan & BTN_MASK) == BTN_LONG_PRESSED) {
            event = BTN3_LONG_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        if (((scan >> BTN_SHIFT) & BTN_MASK) == BTN_SHORT_PRESSED) {
            event = BTN2_SHORT_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        else if (((scan >> BTN_SHIFT) & BTN_MASK) == BTN_LONG_PRESSED) {
            event = BTN2_LONG_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        if (((scan >> (BTN_SHIFT * 2)) & BTN_MASK) == BTN_SHORT_PRESSED) {
            event = BTN1_SHORT_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        else if (((scan >> (BTN_SHIFT * 2)) & BTN_MASK) == BTN_LONG_PRESSED) {
            event = BTN1_LONG_PRESSED;
            xQueueSend(btn_queue, &event, 0);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
