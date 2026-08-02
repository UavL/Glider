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
#include "autoclear.h"
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

#define OSD_WIDTH           CASTER_OSD_WIDTH
#define OSD_HEIGHT          CASTER_OSD_HEIGHT
#define OSD_STATUS_WIDTH    320
#define OSD_STATUS_HEIGHT   64
#define OSD_BLACK           false
#define OSD_WHITE           true
#define NO_SIGNAL_DELAY_MS  5000
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

typedef enum {
    SIGNAL_OSD_NONE,
    SIGNAL_OSD_NO_SIGNAL,
    SIGNAL_OSD_UNSUPPORTED,
    SIGNAL_OSD_SLEEPING,
} signal_osd_state_t;

static void apply_input_selection(bool *tmds_mode, bool reinit_frontends);

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
    if (SPIFFS_errno(&spiffs_fs) != 0) {
        syslog_printf("OSD font '%s' open failed: %d", fn,
                SPIFFS_errno(&spiffs_fs));
        return NULL;
    }

    spiffs_stat s;
    SPIFFS_fstat(&spiffs_fs, f, &s);
    uint32_t size = s.size;

    uint8_t *buf = pvPortMalloc(size);
    if (!buf) {
        SPIFFS_close(&spiffs_fs, f);
        syslog_printf("OSD font '%s': alloc of %u bytes failed", fn,
                (unsigned)size);
        return NULL;
    }

    SPIFFS_read(&spiffs_fs, f, buf, size);
    SPIFFS_close(&spiffs_fs, f);

    const osd_font_t *font = osd_font_from_memory(buf, size);
    if (font == NULL) {
        vPortFree(buf);
        syslog_printf("OSD font '%s': invalid format (%u bytes)", fn,
                (unsigned)size);
        return NULL;
    }

    syslog_printf("OSD font '%s' loaded", fn);
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
    char textbuf[80];
    snprintf(textbuf, 80, "%s %s", title, value);
    osd_draw_prop_string(font_or(fonts->large, fonts->item), 12, 14, textbuf,
            OSD_STATUS_WIDTH - 24, OSD_BLACK);
    caster_osd_set_window(0, 0, OSD_STATUS_WIDTH, OSD_STATUS_HEIGHT);
    caster_osd_send_buf(osd_fb);
    caster_osd_set_enable(true);
}

static void draw_signal_popup(const osd_fonts_t *fonts, const char *title,
        const char *detail) {
    osd_clear(0xff);
    osd_draw_prop_string(font_or(fonts->large, fonts->item), 12, 12, title,
            OSD_STATUS_WIDTH - 24, OSD_BLACK);
    if ((detail != NULL) && (detail[0] != '\0')) {
        osd_draw_prop_string(font_or(fonts->item, fonts->small), 12, 42, detail,
                OSD_STATUS_WIDTH - 24, OSD_BLACK);
    }
    caster_osd_set_window(0, 0, OSD_STATUS_WIDTH, OSD_STATUS_HEIGHT);
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
    int text_y = y + ((h > 34) ? 8 : 4);
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
    int rail_y = y + 80;
    int count = ui_menu_modal_count(menu);
    int index = ui_menu_modal_index(menu);
    int tick_step = (count > 1) ? rail_w / (count - 1) : 0;
    int knob_x = rail_x + tick_step * index;

    if (tick_step != 0)
        rail_w = tick_step * (count - 1);

    osd_fill_rect(x, y, w, h, OSD_WHITE);
    osd_draw_rect(x, y, w, h, OSD_BLACK, 3);

    osd_draw_prop_string(font_or(fonts->item, fonts->small), x + 8, y + 10,
            ui_menu_selected_label(menu), w - 16, OSD_BLACK);
    osd_draw_prop_string(font_or(fonts->large, fonts->item), OSD_WIDTH / 2 - 10,
            y + 40, ui_menu_modal_value_label(menu), w - 24, OSD_BLACK);

    osd_fill_rect(rail_x, rail_y - 2, rail_w, 4, OSD_BLACK);
    for (int i = 0; i < count; i++) {
        int tx = rail_x + tick_step * i;
        osd_fill_rect(tx - 1, rail_y - 7, 2, 14, OSD_BLACK);
    }
    osd_fill_rect(knob_x - 6, rail_y - 10, 12, 20, OSD_BLACK);

    osd_draw_prop_string(font_or(fonts->small, fonts->item), rail_x - 8, rail_y + 18,
            "-3", 36, OSD_BLACK);
    osd_draw_right_string(font_or(fonts->small, fonts->item), rail_x + rail_w + 8,
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

    osd_draw_prop_string(font_or(fonts->item, fonts->small), x + 8, y + 8,
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
        osd_draw_prop_string(font_or(fonts->small, fonts->item), x + 11, yy + 2,
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
    osd_draw_prop_string(font_or(fonts->item, fonts->small), 8, 3, "Settings",
            90, OSD_WHITE);
    osd_draw_prop_string(font_or(fonts->small, fonts->item), 110, 7,
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
    osd_draw_prop_string(font_or(fonts->small, fonts->item), 5, OSD_HEIGHT - 20,
            hint, OSD_WIDTH - 48, OSD_BLACK);

    char page[12];
    snprintf(page, sizeof(page), "%d/%d", selected + 1, count);
    osd_draw_right_string(font_or(fonts->small, fonts->item), OSD_WIDTH - 5,
            OSD_HEIGHT - 20, page, 42, OSD_BLACK);

    caster_osd_set_window(0, config.tcon_vact -
        OSD_HEIGHT * (config.osd_scale_2x ? 2u : 1u), OSD_WIDTH, OSD_HEIGHT);
    caster_osd_send_buf(osd_fb);
    caster_osd_set_enable(true);
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

static const char *autoclear_mode_label(void) {
    switch (config.autoclear_mode) {
    case AC_ADAPT:
        return "Adaptive";
    case AC_FIXED:
        return "Fixed";
    case AC_OFF:
    default:
        return "OFF";
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
            (previous->autoclear_mode != config.autoclear_mode) ||
            (previous->autoclear_interval != config.autoclear_interval) ||
            (previous->autoclear_threshold != config.autoclear_threshold) ||
            (previous->osd_scale_2x != config.osd_scale_2x) ||
            (memcmp(previous->button_actions, config.button_actions,
                    sizeof(config.button_actions)) != 0);
}

static void preview_tone_modal(const ui_menu_t *menu) {
    int lightness = config.lightness;
    int contrast = config.contrast;
    int target = ui_menu_modal_tone_target(menu);

    if (target == 0)
        return;

    if (target == 1)
        lightness = ui_menu_modal_preview_value(menu);
    else if (target == 2)
        contrast = ui_menu_modal_preview_value(menu);

    caster_set_tone(lightness, contrast);
}

static void reset_autoclear_state(TickType_t *autoclear_timeout,
        uint32_t *autoclear_damage_counter, uint32_t *autoclear_damage_last) {
    if (autoclear_timeout != NULL)
        *autoclear_timeout = 0;
    autoclear_reset(autoclear_damage_counter, autoclear_damage_last);
}

static void execute_button_action(button_action_t action, const osd_fonts_t *fonts,
        ui_menu_t *menu, bool *menu_open, bool *autoclear,
        TickType_t *osd_timeout, TickType_t *autoclear_timeout,
        uint32_t *autoclear_damage_counter, uint32_t *autoclear_damage_last,
        osd_menu_render_state_t *render_state, int *autoclear_previous_mode,
        bool *tmds_mode) {
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
        reset_autoclear_state(autoclear_timeout, autoclear_damage_counter,
                autoclear_damage_last);
        break;
    case ACT_TOGGLE_AC:
        config.autoclear_mode = autoclear_toggle_mode(config.autoclear_mode,
                autoclear_previous_mode);
        *autoclear = config.autoclear_mode != AC_OFF;
        reset_autoclear_state(autoclear_timeout, autoclear_damage_counter,
                autoclear_damage_last);
        config_save();
        draw_status_popup(fonts, "Auto Clear", autoclear_mode_label());
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
        apply_input_selection(tmds_mode, true);
        draw_status_popup(fonts, "Input", input_label(config.input_sel));
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    case ACT_INPUT_TMDS:
        config.input_sel = INPUT_SEL_TMDS;
        config_save();
        apply_input_selection(tmds_mode, true);
        draw_status_popup(fonts, "Input", input_label(config.input_sel));
        *osd_timeout = xTaskGetTickCount() + pdMS_TO_TICKS(2000);
        break;
    case ACT_INPUT_DP:
        config.input_sel = INPUT_SEL_DP;
        config_save();
        apply_input_selection(tmds_mode, true);
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

// True only when actual video is flowing with the configured timing: TMDS
// PLL locked, the ADV7611's vertical and DE-regeneration filters locked, and
// the measured resolution matching the display config. The bare TMDS lock
// bit (is_tmds_active) asserts as soon as a carrier is present -- long
// before the source has finished mode-setting -- and must not be used to
// decide that the FPGA may switch onto the recovered pixel clock.
static bool is_tmds_video_stable(void) {
    if (!(adv7611_read_reg(HDMI_I2C_ADDR, 0x04) & 0x02))
        return false;
    uint8_t r07 = adv7611_read_reg(HDMI_I2C_ADDR, 0x07);
    // Bit 7: vertical filter locked, bit 5: DE regeneration filter locked
    if ((r07 & 0xa0) != 0xa0)
        return false;
    uint16_t w = ((uint16_t)(r07 & 0x1f) << 8) |
            adv7611_read_reg(HDMI_I2C_ADDR, 0x08);
    uint16_t h = ((uint16_t)(adv7611_read_reg(HDMI_I2C_ADDR, 0x09) & 0x1f) << 8) |
            adv7611_read_reg(HDMI_I2C_ADDR, 0x0a);
    return (w == config.hact) && (h == config.vact);
}

static bool is_dp_active(void) {
    return dp_ready;
}

static bool is_dp_video_active(void) {
    return gpio_get(DP_ACTIVE) == GPIO_PIN_SET;
}

static bool is_video_active(bool tmds_mode) {
    return tmds_mode ? is_tmds_active() : is_dp_video_active();
}

static bool is_selected_video_active(bool tmds_mode) {
    if (config.input_sel == INPUT_SEL_AUTO)
        return is_tmds_active() || is_dp_video_active();
    return is_video_active(tmds_mode);
}

// Gate for handing the FPGA the live source: requires verified-stable video
// (see is_tmds_video_stable), not just a carrier.
static bool is_selected_source_ready(void) {
    switch (config.input_sel) {
    case INPUT_SEL_TMDS:
        return is_tmds_video_stable();
    case INPUT_SEL_DP:
        return is_dp_video_active();
    case INPUT_SEL_AUTO:
    default:
        return is_tmds_video_stable() || is_dp_video_active();
    }
}

static void resume_video_frontends(void);

// Deferred input-mux switch state. Writing CSR_INPUT_CTRL while the selected
// source's link is still training lets the gateware latch clk_epdc onto a
// clock that can die mid-training -- and the mux FSM (vin_source_ctrl) runs
// on that same clock, so it cannot fall back; mux, FSM and CSR stay dead
// until the bitstream is reloaded. apply_input_selection() therefore parks
// the FPGA on the internal source; the ui_task loop issues the real request
// only once the frontend (checked over I2C/GPIO, independent of the FPGA
// clock) has reported the source present for INPUT_SOURCE_STABLE_MS.
#define INPUT_SOURCE_STABLE_MS  500
// After requesting the switch, expect LIVE within this window; otherwise the
// mux may be latched onto a clock that went away -- reload to recover.
#define INPUT_SWITCH_LIVE_TIMEOUT_MS 5000
static bool input_switch_pending;
static bool input_source_stable_tracking;
static TickType_t input_source_stable_since;
static TickType_t input_live_deadline;
// Bitstreams predating the INPUT_CTRL/vin_source_ctrl interface ignore the
// input requests and always read CSR_INPUT_STATUS as 0x00 (the current
// gateware reads at least 0x19 when parked internal: INTERNAL bit plus
// constant-true STABLE/SUPPORTED). On such bitstreams input selection is
// autonomous in hardware, LIVE never asserts, and the live-timeout reload
// would cycle the pipeline forever -- detect and disable the gating.
static bool input_status_legacy;
// Set while the DP-to-LVDS bridge has been powered down because it is not the
// source in use. See park_unused_frontend(); anything that re-powers the video
// frontends must clear it.
static bool ptn3460_parked;

static void issue_pending_input_request(void) {
    switch (config.input_sel) {
    case INPUT_SEL_TMDS:
        syslog_print("Input source stable; requesting TMDS");
        caster_input_request_tmds();
        break;
    case INPUT_SEL_DP:
        syslog_print("Input source stable; requesting DP");
        caster_input_request_dp();
        break;
    case INPUT_SEL_AUTO:
    default:
        syslog_print("Input source stable; requesting auto");
        caster_input_request_auto();
        break;
    }
}

// reinit_frontends: re-initialize the video frontend chips (needed after
// they were powered down, or when the input selection changed). Skip it on
// pipeline reloads with the frontends already up -- an ADV7611 re-init
// toggles HPD and restarts the source's HDMI handshake, destabilizing the
// very signal the deferred switch is waiting for.
static void apply_input_selection(bool *tmds_mode, bool reinit_frontends) {
    input_switch_pending = true;
    input_source_stable_tracking = false;
    input_live_deadline = 0;
    switch (config.input_sel) {
    case INPUT_SEL_TMDS:
        *tmds_mode = true;
        syslog_print("Requesting TMDS input");
        if (reinit_frontends) {
            adv7611_early_init();
            adv7611_init();
            ptn3460_powerdown();
            ptn3460_parked = true;
        }
        caster_input_force_internal();
        break;
    case INPUT_SEL_DP:
        *tmds_mode = false;
        syslog_print("Requesting DP input");
        if (reinit_frontends) {
            ptn3460_init();
            usbpd_resume_displayport();
            adv7611_powerdown();
            ptn3460_parked = false;
        }
        caster_input_force_internal();
        break;
    case INPUT_SEL_AUTO:
    default:
        if (is_tmds_active())
            *tmds_mode = true;
        else if (is_dp_active())
            *tmds_mode = false;
        syslog_print("Requesting auto input");
        if (reinit_frontends)
            resume_video_frontends();
        caster_input_force_internal();
        break;
    }
}

// How long to wait for CSR access after a successful configuration before
// concluding the FPGA is wedged and rebooting to recover (a reboot also
// clears any leaked filesystem state). A failed bitstream load never gets
// here -- it parks in fatal() instead, so this cannot reboot-loop on a
// missing file.
#define FPGA_CSR_WAIT_TIMEOUT_MS 5000

static void restart_fpga(void) {
    if (fpga_init(config.bitstream) != 0) {
        // No bitstream reached the FPGA; waiting for CSR access would hang
        // forever. Park in a safe, debuggable state (EPD off, shell alive).
        fatal("Bitstream load failed; check 'fpga.bit' with 'fs ls'");
    }
    syslog_printf("Waiting for FPGA CSR access");
    uint32_t waited = 0;
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(100));
        waited += 100;
        uint8_t result = fpga_write_reg8(CSR_ID0, 0x00);
        if (result == 0x35) {
            break;
        }
        if (waited >= FPGA_CSR_WAIT_TIMEOUT_MS) {
            syslog_print("FPGA CSR unresponsive after load; resetting");
            power_off_epd();
            NVIC_SystemReset();
        }
    }
    syslog_printf("FPGA up");
}

// After configuration the FPGA's DDR3 controller can fail calibration
// intermittently (observed on hardware: CSR_STATUS 0x90 = MIG_ERROR +
// OP_BUSY, no SYS_READY, after a resume that left the still-powered DDR3
// chip unrefreshed). Wait for SYS_READY and retry the configuration once
// instead of handing the ui loop's reset safety net a sick FPGA.
#define FPGA_READY_TIMEOUT_MS   1000
#define FPGA_READY_POLL_MS      20

static void wait_fpga_ready(void) {
    const uint8_t err_mask =
            (uint8_t)((1u << STATUS_MIG_ERROR) | (1u << STATUS_MIF_ERROR));

    for (int attempt = 0; ; attempt++) {
        uint8_t status = fpga_write_reg8(CSR_STATUS, 0x00);
        uint32_t waited = 0;
        while (!(status & (1u << STATUS_SYS_READY)) &&
                !(status & err_mask) && (waited < FPGA_READY_TIMEOUT_MS)) {
            sleep_ms(FPGA_READY_POLL_MS);
            waited += FPGA_READY_POLL_MS;
            status = fpga_write_reg8(CSR_STATUS, 0x00);
        }
        if (status & (1u << STATUS_SYS_READY))
            return;
        if (attempt >= 1) {
            syslog_printf("FPGA not ready (status %02x); giving up", status);
            return;
        }
        syslog_printf("FPGA not ready (status %02x); reloading bitstream",
                status);
        restart_fpga();
    }
}

static void start_display_pipeline(bool *tmds_mode, const osd_fonts_t *fonts,
        signal_osd_state_t *signal_osd_state, TickType_t *no_signal_deadline,
        bool reinit_frontends) {
    // The DDR3 controller can come up sick on the resume path (observed:
    // status 0x90 = MIG_ERROR + OP_BUSY appearing only after the pipeline
    // starts generating memory traffic -- the early wait_fpga_ready() check
    // passes). Verify the final status; retry the configuration once, and
    // if it is still failing, reboot: a clean boot is known to recalibrate.
    const uint8_t err_mask =
            (uint8_t)((1u << STATUS_MIG_ERROR) | (1u << STATUS_MIF_ERROR));

    for (int attempt = 0; ; attempt++) {
        restart_fpga();
        wait_fpga_ready();
        power_on_epd();
        caster_init();
        apply_input_selection(tmds_mode, reinit_frontends);
        caster_osd_set_enable(false);
        *signal_osd_state = SIGNAL_OSD_NONE;
        *no_signal_deadline = xTaskGetTickCount() +
                pdMS_TO_TICKS(NO_SIGNAL_DELAY_MS);

        uint8_t status = fpga_write_reg8(CSR_STATUS, 0x00);
        syslog_printf("FPGA started with status %02x", status);
        if (((status & err_mask) == 0) &&
                ((status & (1u << STATUS_SYS_READY)) != 0))
            break;
        if (attempt >= 1) {
            syslog_print("FPGA memory interface still failing; resetting");
            power_off_epd();
            NVIC_SystemReset();
        }
        syslog_print("FPGA memory interface unhealthy; retrying configuration");
        power_off_epd();
    }

    input_status_legacy = (caster_input_status() == 0x00);
    if (input_status_legacy)
        syslog_print("Legacy bitstream: no input-control interface; "
                "live-source gating disabled");
}

static void resume_video_frontends(void) {
    adv7611_early_init();
    adv7611_init();
    ptn3460_init();
    usbpd_resume_displayport();
    ptn3460_parked = false;
}

// INPUT_SEL_AUTO brings both video frontends up unconditionally, so the
// PTN3460 stays powered on +1V8_VID for the whole session even when the source
// is HDMI and the bridge has nothing to do. Nothing about DP *detection* runs
// through it -- a DP source announces itself over USB-PD (dp_ready) and on the
// DP_ACTIVE pin -- so it can be parked until DP actually shows up. The explicit
// TMDS and DP selections already do the equivalent in apply_input_selection().
static void park_unused_frontend(uint8_t input_status) {
    if (config.input_sel != INPUT_SEL_AUTO)
        return;

    bool dp_present = is_dp_active() || is_dp_video_active() ||
            !!(input_status & INPUT_STATUS_DP);

    if (dp_present) {
        if (ptn3460_parked) {
            syslog_print("DP source appeared; restoring the DP bridge");
            ptn3460_init();
            ptn3460_parked = false;
        }
        return;
    }

    // Only park once the FPGA has actually settled on the TMDS source, so a
    // still-negotiating DP link is never mistaken for "HDMI won".
    bool tmds_selected = ((input_status & INPUT_STATUS_TMDS) != 0) &&
            ((input_status & INPUT_STATUS_LIVE) != 0);
    if (!ptn3460_parked && tmds_selected) {
        syslog_print("Auto input settled on TMDS; parking the DP bridge");
        ptn3460_powerdown();
        ptn3460_parked = true;
    }
}

static void update_input_tracking(uint8_t input_status, bool *tmds_mode,
        bool *live_was_selected) {
    if (input_status & INPUT_STATUS_TMDS)
        *tmds_mode = true;
    else if (input_status & INPUT_STATUS_DP)
        *tmds_mode = false;
    *live_was_selected = !!(input_status & INPUT_STATUS_LIVE);
}

static void update_signal_osd(const osd_fonts_t *fonts, uint8_t input_status,
        bool menu_open, TickType_t osd_timeout,
        signal_osd_state_t *signal_osd_state, TickType_t *no_signal_deadline) {
    if (menu_open || (osd_timeout != 0))
        return;

    if (input_status & INPUT_STATUS_LIVE) {
        if (*signal_osd_state != SIGNAL_OSD_NONE)
            caster_osd_set_enable(false);
        *signal_osd_state = SIGNAL_OSD_NONE;
        *no_signal_deadline = 0;
        return;
    }

    if ((input_status & INPUT_STATUS_STABLE) &&
            !(input_status & INPUT_STATUS_SUPPORTED)) {
        if (*signal_osd_state != SIGNAL_OSD_UNSUPPORTED) {
            uint16_t hact;
            uint16_t vact;
            char detail[32];
            caster_input_get_measured(&hact, &vact, NULL, NULL);
            if ((hact != 0) && (vact != 0))
                snprintf(detail, sizeof(detail), "%u x %u", hact, vact);
            else
                detail[0] = '\0';
            draw_signal_popup(fonts, "Unsupported Input", detail);
            *signal_osd_state = SIGNAL_OSD_UNSUPPORTED;
        }
        *no_signal_deadline = 0;
        return;
    }

    if ((*no_signal_deadline != 0) &&
            (((int32_t)xTaskGetTickCount() - (int32_t)*no_signal_deadline) < 0)) {
        if (*signal_osd_state != SIGNAL_OSD_NONE)
            caster_osd_set_enable(false);
        *signal_osd_state = SIGNAL_OSD_NONE;
        return;
    }
    *no_signal_deadline = 0;

    if (*signal_osd_state != SIGNAL_OSD_NO_SIGNAL) {
        draw_signal_popup(fonts, "No Signal", NULL);
        *signal_osd_state = SIGNAL_OSD_NO_SIGNAL;
    }
}

static void log_input_status(uint8_t input_status) {
    uint16_t hact;
    uint16_t vact;
    uint16_t htotal;
    uint16_t vtotal;

    caster_input_get_measured(&hact, &vact, &htotal, &vtotal);
    syslog_printf("Input status %02x, measured %u x %u, total %u x %u",
            input_status, hact, vact, htotal, vtotal);
}

static void reload_to_internal_source(bool *tmds_mode, const osd_fonts_t *fonts,
        signal_osd_state_t *signal_osd_state, TickType_t *no_signal_deadline,
        const char *reason) {
    syslog_print(reason);
    power_off_epd();
    start_display_pipeline(tmds_mode, fonts, signal_osd_state,
            no_signal_deadline, false);
}

static void recover_from_live_loss(bool *tmds_mode, const osd_fonts_t *fonts,
        signal_osd_state_t *signal_osd_state, TickType_t *no_signal_deadline) {
    reload_to_internal_source(tmds_mode, fonts, signal_osd_state,
            no_signal_deadline,
            "Live video lost; reloading FPGA into internal source");
    draw_signal_popup(fonts, "Sleeping", NULL);
    *signal_osd_state = SIGNAL_OSD_SLEEPING;
    *no_signal_deadline = 0;
    caster_redraw(0, 0, config.hact, config.vact);
    sleep_ms(600);
    power_suspend(POWER_SUSPEND_VIDEO_LOSS);
}

static uint32_t wait_for_wake_source(bool *usbpd_wake_armed,
        TickType_t usbpd_wake_arm_time, bool tmds_mode) {
    btn_event_t btn_event;
    power_suspend_reason_t reason = power_get_current_suspend_reason();

    if (power_take_request() == POWER_REQ_RESUME)
        return POWER_WAKE_USB;

    if ((reason == POWER_SUSPEND_VIDEO_LOSS) && is_selected_video_active(tmds_mode))
        return POWER_WAKE_INPUT;

    if (usbapp_take_resume_event())
        return POWER_WAKE_USB;

    if (xQueueReceive(btn_queue, &btn_event, pdMS_TO_TICKS(200)) == pdTRUE)
        return POWER_WAKE_BUTTON;

    if (usbapp_take_resume_event())
        return POWER_WAKE_USB;

    if (!*usbpd_wake_armed &&
            (((int32_t)xTaskGetTickCount() - (int32_t)usbpd_wake_arm_time) >= 0)) {
        usbpd_arm_wake();
        *usbpd_wake_armed = true;
    }

    if (*usbpd_wake_armed && usbpd_take_wake_event())
        return POWER_WAKE_USB_PD;
    return POWER_WAKE_NONE;
}

// Retain suspend: EPD rails off with the last image kept on the panel,
// while the FPGA, framebuffer and video frontends stay alive for fast
// resume. Entered on host request (USB HID / shell).
#define RETAIN_POLL_MS          30
#define RETAIN_QUIET_MS         120
#define RETAIN_QUIET_TIMEOUT_MS 2000
#define RETAIN_SETTLE_MS        700
#define RETAIN_CASTER_IDLE_MS   1000
// The auto-LUT engine keeps driving the glass long after the damage counter
// goes quiet. The gateware waits AUTOLUT_QUIET_FRAMES (60) of *global* quiet
// before it releases the shared greyscale phase, then follows the waveform
// for CSR_LUT_FRAME (38) frames -- ~1.63 s at 60 Hz. Neither phase asserts
// pixel_diff, so the damage counter reads zero throughout and cannot see any
// of it; the wait has to be open-loop. RETAIN_SETTLE_MS alone cut the rails
// before the greyscale phase had even started.
#define RETAIN_SETTLE_AUTOLUT_MS 1950
#define RETAIN_IDLE_TIMEOUT_MS  1000
// How often the retained loop re-checks that the video frontend still has a
// signal. The damage counter has to be polled at RETAIN_POLL_MS (it is a
// per-frame count and a page turn only marks one frame), but the frontend
// probe is an I2C transaction and does not.
#define RETAIN_VIDEO_CHECK_MS   1000
static TickType_t retain_video_check_due;
// Upper bound on the closed-loop settle wait once STATUS_PANEL_ACTIVE is
// trustworthy (CASTER_FEATURE_HOLD). Comfortably longer than the worst case
// the open-loop wait was sized for; it should never be reached.
#define RETAIN_SETTLE_TIMEOUT_MS 4000
// Experimental: stop the panel scan engine as well while retained. Off by
// default so it can be enabled and backed out from the shell without a
// reflash. See caster_set_refresh().
static bool retain_scan_stop;

void ui_set_retain_scan_stop(bool enable) {
    retain_scan_stop = enable;
}

bool ui_get_retain_scan_stop(void) {
    return retain_scan_stop;
}

// Wake threshold while retained, in damage-counter units. The counter tracks
// groups of four horizontally adjacent pixels, so the full panel is
// hact/4 * vact; wake on about one percent of it. A KOReader page turn is far
// above that and a blinking cursor far below, which is what stops retain from
// bouncing straight back to active under any activity at all.
static uint32_t retain_damage_threshold(void) {
    uint32_t groups = ((uint32_t)config.hact / 4u) * (uint32_t)config.vact;
    uint32_t threshold = groups / 100u;
    return (threshold == 0) ? 1u : threshold;
}

// While a video source is present at the frontend but the FPGA has not yet
// reported it live, the EPDC (CSR interface included) can be clocked from the
// still-training input pixel clock, making register access unreliable. Hold
// off FPGA traffic in that window instead of treating a failed read as a lost
// FPGA; give up after the grace period so a genuinely hung FPGA is still
// caught by the reset safety net.
#define INPUT_ACQUIRE_GRACE_MS  3000
#define INPUT_ACQUIRE_POLL_MS   100

// How long CSR access may stay dead before the pipeline is reloaded. The
// CSR interface rides the video input clock; once the mux has left the
// internal source, a clock loss (cable pull, source renegotiation) freezes
// the gateware mux FSM on the dead clock and nothing inside the FPGA can
// recover it -- only a reconfiguration. Waiting longer than a couple of
// seconds just prolongs the outage.
#define FPGA_CSR_DEAD_LIMIT_MS  2000

// How long the panel may still be driven after the last observable change,
// for the mode currently configured.
static uint32_t retain_settle_ms(void) {
    switch (config.update_mode) {
    case UM_AUTO_LUT_NO_DITHER:
    case UM_AUTO_LUT_ERROR_DIFFUSION:
        return RETAIN_SETTLE_AUTOLUT_MS;
    default:
        return RETAIN_SETTLE_MS;
    }
}

static bool enter_retain(bool damage_wake, uint32_t *damage_last,
        uint32_t *damage_accum) {
    uint32_t quiet_ms = 0;
    uint32_t waited_ms = 0;
    uint32_t damage = caster_get_damage_counter();

    *damage_accum = 0;
    retain_video_check_due = xTaskGetTickCount();

    syslog_print("Entering retain suspend");
    caster_osd_set_enable(false);

    bool hold_works = caster_has_feature(CASTER_FEATURE_HOLD);

    // Wait for input-driven updates to go quiet so the retained image is
    // complete. Give up eventually and retain anyway; the resume redraw
    // reconciles anything that was cut short.
    while (quiet_ms < RETAIN_QUIET_MS) {
        if (waited_ms >= RETAIN_QUIET_TIMEOUT_MS) {
            syslog_print("Input still changing; retaining anyway");
            break;
        }
        sleep_ms(RETAIN_POLL_MS);
        waited_ms += RETAIN_POLL_MS;
        uint32_t now = caster_get_damage_counter();
        if (now != damage) {
            damage = now;
            quiet_ms = 0;
        }
        else {
            quiet_ms += RETAIN_POLL_MS;
        }
    }

    // Wait for queued host operations (redraw/setmode) to be consumed
    if (caster_wait_idle(RETAIN_CASTER_IDLE_MS) != 0)
        syslog_print("Caster op still busy; retaining anyway");

    // Only now stop the framebuffer from following the input. In-flight
    // waveforms still run their per-pixel frame counters to zero -- freezing
    // writeback instead would strand those counters mid-sequence -- but
    // nothing new starts, so the state settles and then stays put for the
    // whole retain. That is what keeps the framebuffer and the glass in
    // agreement while the rails are off, and it is why resume needs no redraw.
    //
    // Ordering matters: this has to come *after* the input has gone quiet.
    // Holding first would freeze the framebuffer part-way through a page
    // being drawn, and those pixels would then read as permanently differing
    // from the input -- an immediate spurious damage wake, every time.
    //
    // Hold used to be mutually exclusive with damage wake, because the damage
    // counter only registered transition *starts* and hold suppresses those.
    // With CASTER_FEATURE_HOLD the gateware reports a held pixel that differs
    // from the input as damage without acting on it, so the counter reads
    // "pixels that no longer match the glass" and the two work together.
    // On older gateware the write is ignored and the resume-time redraw below
    // is still the only backstop.
    caster_set_hold(true);

    // Let in-flight per-pixel waveforms finish on glass before cutting rails.
    // With a trustworthy STATUS_PANEL_ACTIVE this is closed-loop and usually
    // much shorter than the open-loop wait it replaces; the timeout is only a
    // backstop. Without it the bit reads 0 always, so the fixed sleep is the
    // only thing standing between the auto-LUT greyscale phase and dead rails.
    uint32_t idle_ms = 0;
    uint32_t idle_timeout = RETAIN_IDLE_TIMEOUT_MS;
    if (hold_works) {
        idle_timeout = RETAIN_SETTLE_TIMEOUT_MS;
    }
    else {
        sleep_ms(retain_settle_ms());
    }
    while (caster_panel_active()) {
        if (idle_ms >= idle_timeout) {
            syslog_print("Panel still driving; retaining anyway");
            break;
        }
        sleep_ms(RETAIN_POLL_MS);
        idle_ms += RETAIN_POLL_MS;
    }
    if (hold_works)
        syslog_printf("Panel settled after %u ms", (unsigned)idle_ms);

    // The counter means different things on the two gatewares: a level ("how
    // much of the image no longer matches the glass", starts at zero because
    // the panel just settled) versus a per-frame edge count. Seed accordingly.
    *damage_last = hold_works ? 0u : caster_get_damage_counter();

    // Stopping the scan is the only thing here that reduces the FPGA's draw,
    // but it also freezes the damage counter, so it cannot coexist with waking
    // on image change.
    if (retain_scan_stop && hold_works && !damage_wake) {
        syslog_print("Stopping panel scan for retain");
        caster_set_refresh(false);
    }

    power_suspend(POWER_SUSPEND_RETAIN);
    return power_is_retained();
}

static uint32_t wait_for_retain_wake(bool tmds_mode, bool damage_wake,
        uint32_t *damage_last, uint32_t *damage_accum) {
    btn_event_t btn_event;

    power_request_t req = power_take_request();
    if (req == POWER_REQ_RESUME)
        return POWER_WAKE_USB;
    if (req == POWER_REQ_SUSPEND) {
        power_retain_deepen(POWER_SUSPEND_USER);
        return POWER_WAKE_NONE;
    }

    if (usbapp_take_suspend_event()) {
        syslog_print("USB bus suspended; deepening retain suspend");
        power_retain_deepen(POWER_SUSPEND_USB);
        return POWER_WAKE_NONE;
    }
    (void)usbapp_take_resume_event();

    // With live video selected the FPGA runs off the input clock, so check
    // the frontends (MCU-side) before touching FPGA registers. That check is
    // an ADV7611 register read over I2C, and at the RETAIN_POLL_MS rate it was
    // the most expensive thing the retained system did -- retain kept the MCU
    // busier than being awake. Video does not disappear on a 30 ms timescale,
    // so probe it about once a second instead.
    TickType_t now = xTaskGetTickCount();
    if ((int32_t)(now - retain_video_check_due) >= 0) {
        retain_video_check_due = now + pdMS_TO_TICKS(RETAIN_VIDEO_CHECK_MS);
        if (!is_selected_video_active(tmds_mode)) {
            syslog_print("Video lost during retain; deepening retain suspend");
            power_retain_deepen(POWER_SUSPEND_VIDEO_LOSS);
            return POWER_WAKE_NONE;
        }
    }

    if (caster_has_feature(CASTER_FEATURE_HOLD)) {
        // Held, so the counter is a level: how much of the image currently
        // differs from what is on the glass. It stays asserted until the
        // difference is resolved, so a slow poll cannot miss a page turn, and
        // a threshold filters out cursor blinks instead of waking on one pixel.
        uint32_t damage = caster_get_damage_counter();
        *damage_accum = damage;
        if (damage_wake && (damage > retain_damage_threshold()))
            return POWER_WAKE_DAMAGE;
    }
    else {
        // CSR_DAMAGE_COUNT is a per-frame count -- the gateware zeroes it every
        // vsync -- so accumulate the samples to measure how much of the image
        // changed while retained. Comparing snapshots taken at retain entry and
        // at resume reads ~0 in both cases (the image is quiet at each end) and
        // never detects the change in between.
        uint32_t damage = caster_get_damage_counter();
        if (damage != 0) {
            uint32_t accum = *damage_accum + damage;
            *damage_accum = (accum < *damage_accum) ? 0xffffffffu : accum;
        }

        if (damage_wake && (damage != *damage_last)) {
            *damage_last = damage;
            return POWER_WAKE_DAMAGE;
        }
    }

    if (xQueueReceive(btn_queue, &btn_event,
            pdMS_TO_TICKS(RETAIN_POLL_MS)) == pdTRUE)
        return POWER_WAKE_BUTTON;

    return POWER_WAKE_NONE;
}

portTASK_FUNCTION(ui_task, pvParameters) {
    TickType_t osd_timeout = 0;
    TickType_t autoclear_timeout = 0;
    uint32_t autoclear_damage_counter = 0;
    uint32_t autoclear_damage_last = 0;
    int autoclear_previous_mode = (config.autoclear_mode == AC_ADAPT ||
            config.autoclear_mode == AC_FIXED) ? config.autoclear_mode : AC_ADAPT;
    bool autoclear = config.autoclear_mode != AC_OFF;
    bool menu_open = false;
    bool suspend_wait_initialized = false;
    bool usbpd_wake_armed = false;
    bool retain_damage_wake = true;
    uint32_t retain_damage_last = 0;
    uint32_t retain_damage_accum = 0;
    bool live_was_selected = false;
    TickType_t input_acquire_deadline = 0;
    uint8_t last_logged_input_status = 0xff;
    TickType_t no_signal_deadline = 0;
    TickType_t usbpd_wake_arm_time = 0;
    ui_menu_t menu;
    osd_menu_render_state_t menu_render_state = {0};
    signal_osd_state_t signal_osd_state = SIGNAL_OSD_NONE;

    osd_fonts_t fonts = {
        .small = load_osd_font("fonts/font_quicksand_16.bin"),
        .item = load_osd_font("fonts/font_quicksand_20.bin"),
        .large = load_osd_font("fonts/font_quicksand_28.bin"),
    };

    mode = mode_index_for((update_mode_t)config.update_mode);

    bool tmds_mode = false;
    start_display_pipeline(&tmds_mode, &fonts, &signal_osd_state,
            &no_signal_deadline, true);

    while (1) {
        if (power_is_suspended()) {
            uint32_t wake_sources;

            if (power_is_retained()) {
                // Re-run the deep-wait init below if the state deepens
                suspend_wait_initialized = false;
                wake_sources = wait_for_retain_wake(tmds_mode,
                        retain_damage_wake, &retain_damage_last,
                        &retain_damage_accum);
            }
            else {
                if (!suspend_wait_initialized) {
                    usbpd_disarm_wake();
                    usbpd_wake_armed = false;
                    usbpd_wake_arm_time = xTaskGetTickCount() + pdMS_TO_TICKS(1000);
                    suspend_wait_initialized = true;
                }

                wake_sources = wait_for_wake_source(&usbpd_wake_armed,
                        usbpd_wake_arm_time, tmds_mode);
            }
            if (!power_request_resume(wake_sources))
                continue;

            syslog_printf("Waking system: 0x%02x", (unsigned)wake_sources);
            if (power_get_last_suspend_reason() == POWER_SUSPEND_RETAIN) {
                // Fast path: FPGA, framebuffer and video frontends were kept
                // alive; only the EPD rails were off.
                //
                // Without CASTER_EN_HOLD the EPDC kept scanning while
                // retained, so anything that changed on the input was
                // consumed with the rails dead: the framebuffer advanced for
                // pixels the glass never moved, and the two are now out of
                // sync. Repainting differentially from that baseline
                // superimposes the old and new images, so a meaningful
                // change needs a full redraw -- OP_EXT_REDRAW force-clears
                // every pixel before repainting, which puts glass and
                // framebuffer back in agreement.
                //
                // Small churn (cursor blink, a clock digit) is left alone --
                // those pixels stay stale until they next change, which is
                // the price of a flash-free resume.
                //
                // With hold supported none of that applies: the framebuffer
                // never diverged, so releasing the hold is the entire resume.
                // Whatever changed on the input is repainted as an ordinary
                // per-pixel update -- no clear phase, no flash.
                power_on_epd();
                // Restart the scan before releasing the hold, so the first
                // frame the pixels see is a real one.
                caster_set_refresh(true);
                // Release the hold before any redraw: while held, pixels
                // ignore input changes, so a redraw issued first would be
                // suppressed along with everything else.
                caster_set_hold(false);
                if (caster_has_feature(CASTER_FEATURE_HOLD)) {
                    if (retain_damage_accum != 0)
                        syslog_printf("Image changed during retain (%u); "
                                "repainting", (unsigned)retain_damage_accum);
                }
                else if (retain_damage_accum >
                        ((uint32_t)config.hact * config.vact) / 100u) {
                    syslog_printf("Image changed during retain (%u); "
                            "redrawing", (unsigned)retain_damage_accum);
                    caster_redraw(0, 0, config.hact, config.vact);
                }
                power_resume_complete();
                suspend_wait_initialized = false;
                reset_autoclear_state(&autoclear_timeout,
                        &autoclear_damage_counter, &autoclear_damage_last);
                continue;
            }
            usbpd_disarm_wake();
            fpga_resume();
            if (power_get_last_suspend_reason() != POWER_SUSPEND_VIDEO_LOSS)
                resume_video_frontends();
            start_display_pipeline(&tmds_mode, &fonts, &signal_osd_state,
                    &no_signal_deadline, false);
            power_resume_complete();

            menu_open = false;
            suspend_wait_initialized = false;
            usbpd_wake_armed = false;
            live_was_selected = false;
            input_acquire_deadline = 0;
            osd_timeout = 0;
            autoclear_timeout = 0;
            autoclear = config.autoclear_mode != AC_OFF;
            mode = mode_index_for((update_mode_t)config.update_mode);
            reset_autoclear_state(&autoclear_timeout, &autoclear_damage_counter,
                    &autoclear_damage_last);
            menu_render_state.first_row = 0;
            menu_render_state.category_index = 0;
            menu_render_state.depth = UI_MENU_DEPTH_CATEGORIES;
            continue;
        }

        (void)usbapp_take_resume_event();
        if (usbapp_take_suspend_event()) {
            syslog_print("USB bus suspended; suspending");
            power_suspend(POWER_SUSPEND_USB);
            continue;
        }

        power_request_t power_req = power_take_request();
        if (power_req == POWER_REQ_SUSPEND) {
            syslog_print("Host requested suspend");
            power_suspend(POWER_SUSPEND_USER);
            continue;
        }
        if ((power_req == POWER_REQ_RETAIN) ||
                (power_req == POWER_REQ_RETAIN_NOWAKE)) {
            syslog_print("Host requested retain suspend");
            retain_damage_wake = (power_req == POWER_REQ_RETAIN);
            menu_open = false;
            osd_timeout = 0;
            enter_retain(retain_damage_wake, &retain_damage_last,
                    &retain_damage_accum);
            continue;
        }

        // Deferred input-mux switch (see the comment at
        // issue_pending_input_request): only hand the FPGA the live source
        // once the frontend has reported verified-stable video (locked
        // filters + matching measured resolution) continuously.
        if (input_switch_pending && !live_was_selected) {
            if (!is_selected_source_ready()) {
                input_source_stable_tracking = false;
            }
            else if (!input_source_stable_tracking) {
                input_source_stable_tracking = true;
                input_source_stable_since = xTaskGetTickCount();
            }
            else if (((int32_t)xTaskGetTickCount() -
                    (int32_t)(input_source_stable_since +
                    pdMS_TO_TICKS(INPUT_SOURCE_STABLE_MS))) >= 0) {
                issue_pending_input_request();
                input_switch_pending = false;
                input_source_stable_tracking = false;
                input_acquire_deadline = 0;
                input_live_deadline = input_status_legacy ? 0 :
                        (xTaskGetTickCount() +
                        pdMS_TO_TICKS(INPUT_SWITCH_LIVE_TIMEOUT_MS));
            }
        }

        // If the switch was issued but the pipeline never reached LIVE, the
        // mux may be latched onto a clock that went away (the gateware FSM
        // cannot fall back on its own). Reload to get back to a known state;
        // apply_input_selection() re-arms the deferred switch.
        if (!input_switch_pending && !live_was_selected &&
                (input_live_deadline != 0) &&
                (((int32_t)xTaskGetTickCount() -
                (int32_t)input_live_deadline) >= 0)) {
            input_live_deadline = 0;
            reload_to_internal_source(&tmds_mode, &fonts, &signal_osd_state,
                    &no_signal_deadline,
                    "Input did not go live after switch; reloading pipeline");
            live_was_selected = false;
            input_acquire_deadline = 0;
            last_logged_input_status = 0xff;
            continue;
        }

        // Input acquisition window: a source is present at the frontend but
        // the FPGA has not confirmed live video yet (fresh resume, cable
        // plug-in, host mode change). Probe the CSR bus first and skip the
        // whole FPGA-touching part of this iteration while it is
        // unresponsive, so a training input clock neither triggers the
        // reset safety net below nor feeds garbage into autoclear/input
        // tracking.
        bool input_acquiring = !live_was_selected &&
                is_selected_video_active(tmds_mode);
        bool acquire_grace = false;
        if (!input_acquiring) {
            input_acquire_deadline = 0;
        }
        else {
            if (input_acquire_deadline == 0)
                input_acquire_deadline = xTaskGetTickCount() +
                        pdMS_TO_TICKS(INPUT_ACQUIRE_GRACE_MS);
            acquire_grace = ((int32_t)xTaskGetTickCount() -
                    (int32_t)input_acquire_deadline) < 0;
            if (acquire_grace &&
                    (fpga_write_reg8(CSR_ID0, 0x00) != 0x35)) {
                vTaskDelay(pdMS_TO_TICKS(INPUT_ACQUIRE_POLL_MS));
                continue;
            }
        }

        // Check OSD timeout
        if ((osd_timeout != 0) && (((int32_t)xTaskGetTickCount() - (int32_t)osd_timeout) >= 0)) {
            osd_timeout = 0;
            caster_osd_set_enable(false);
        }

        // Update auto clear
        bool autoclear_trigger = false;
        if (autoclear && (config.autoclear_mode == AC_ADAPT)) {
            autoclear_trigger = autoclear_adaptive_update(
                    &autoclear_damage_counter, &autoclear_damage_last,
                    caster_get_damage_counter(), config.autoclear_threshold,
                    config.hact, config.vact);
        }

        if ((autoclear_timeout != 0) && (((int32_t)xTaskGetTickCount() - (int32_t)autoclear_timeout) >= 0)) {
            autoclear_trigger = true;
            autoclear_timeout = 0; // Pending reset
        }

        if (autoclear_trigger) {
            caster_redraw(0, 0, config.hact, config.vact);
            reset_autoclear_state(&autoclear_timeout, &autoclear_damage_counter,
                    &autoclear_damage_last);
        }

        // Arm the interval timer in adaptive mode too. Adaptive reads a
        // per-frame damage counter (the gateware zeroes it every vsync) from
        // this ~200 ms loop, so at 75 Hz it only sees about one frame in
        // fifteen and misses most page turns; without a backstop it can go a
        // very long time without clearing. Whichever fires first wins.
        if (autoclear && (autoclear_timeout == 0)) {
            autoclear_timeout = xTaskGetTickCount() +
                    pdMS_TO_TICKS(autoclear_fixed_interval_ms(
                            config.autoclear_interval));
        }

        if (!autoclear) {
            reset_autoclear_state(&autoclear_timeout, &autoclear_damage_counter,
                    &autoclear_damage_last);
        }

        // Detect loss of signal / lost access to FPGA. If live video was
        // selected, a stopped external clock can also stop CSR access, so use
        // the frontend signal check before touching FPGA registers.
        if (live_was_selected && !is_video_active(tmds_mode)) {
            recover_from_live_loss(&tmds_mode, &fonts, &signal_osd_state,
                    &no_signal_deadline);
            live_was_selected = false;
            continue;
        }
        if (fpga_write_reg8(CSR_ID0, 0x00) != 0x35) {
            if (acquire_grace) {
                // Input clock dropped between the probe above and here;
                // still inside the acquisition grace period.
                vTaskDelay(pdMS_TO_TICKS(INPUT_ACQUIRE_POLL_MS));
                continue;
            }
            // Debounce: see the FPGA_CSR_DEAD_LIMIT_MS comment for why CSR
            // can drop out transiently. If it stays dead, the mux is latched
            // onto a dead clock and only a reconfiguration recovers it --
            // reload the pipeline instead of rebooting the MCU (keeps the
            // shell and syslog alive; frontends are left running so the
            // source's handshake is not restarted).
            uint32_t dead_ms = 0;
            bool recovered = false;
            while (dead_ms < FPGA_CSR_DEAD_LIMIT_MS) {
                vTaskDelay(pdMS_TO_TICKS(INPUT_ACQUIRE_POLL_MS));
                dead_ms += INPUT_ACQUIRE_POLL_MS;
                if (fpga_write_reg8(CSR_ID0, 0x00) == 0x35) {
                    recovered = true;
                    break;
                }
            }
            if (!recovered) {
                reload_to_internal_source(&tmds_mode, &fonts,
                        &signal_osd_state, &no_signal_deadline,
                        "FPGA access lost; reloading pipeline");
                live_was_selected = false;
                input_acquire_deadline = 0;
                last_logged_input_status = 0xff;
                continue;
            }
            syslog_printf("FPGA CSR recovered after %u ms dropout",
                    (unsigned)dead_ms);
            continue;
        }

        uint8_t input_status = caster_input_status();
        if (input_status != last_logged_input_status) {
            log_input_status(input_status);
            last_logged_input_status = input_status;
        }
        update_input_tracking(input_status, &tmds_mode, &live_was_selected);
        park_unused_frontend(input_status);
        if (live_was_selected)
            input_live_deadline = 0;
        // Suppress the LOST reload only during the acquisition grace period:
        // the reload restarts the frontend handshake it would be waiting on.
        // After the grace expires it must run again, or a source that needs
        // the reload to re-acquire would never come up.
        if ((input_status & INPUT_STATUS_LOST) && !acquire_grace) {
            if (is_selected_video_active(tmds_mode)) {
                reload_to_internal_source(&tmds_mode, &fonts, &signal_osd_state,
                        &no_signal_deadline,
                        "FPGA source lost while frontend is active; retrying internal source");
            }
            else {
                recover_from_live_loss(&tmds_mode, &fonts, &signal_osd_state,
                        &no_signal_deadline);
            }
            live_was_selected = false;
            input_acquire_deadline = 0;
            last_logged_input_status = 0xff;
            continue;
        }
        // On a legacy bitstream the status register is blind -- it would
        // report "no signal" permanently, drawing the popup over perfectly
        // working video (the long-standing white box in the OSD corner).
        if (!input_status_legacy)
            update_signal_osd(&fonts, input_status, menu_open, osd_timeout,
                    &signal_osd_state, &no_signal_deadline);

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
            bool was_tone_modal = ui_menu_modal_is_tone(&menu);

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
                if (was_tone_modal && (menu_event == UI_MENU_EVENT_BACK)) {
                    caster_set_tone(config.lightness, config.contrast);
                }
                else if (ui_menu_modal_is_tone(&menu) &&
                        ((menu_event == UI_MENU_EVENT_PREV) ||
                         (menu_event == UI_MENU_EVENT_NEXT))) {
                    preview_tone_modal(&menu);
                }
                if (menu_config_changed(&previous_config)) {
                    if (previous_config.autoclear_mode != config.autoclear_mode) {
                        if ((config.autoclear_mode == AC_ADAPT) ||
                                (config.autoclear_mode == AC_FIXED)) {
                            autoclear_previous_mode = config.autoclear_mode;
                        }
                        else if ((previous_config.autoclear_mode == AC_ADAPT) ||
                                (previous_config.autoclear_mode == AC_FIXED)) {
                            autoclear_previous_mode = previous_config.autoclear_mode;
                        }
                    }
                    config_save();
                    autoclear = config.autoclear_mode != AC_OFF;
                    if (previous_config.input_sel != config.input_sel) {
                        apply_input_selection(&tmds_mode, true);
                        live_was_selected = false;
                    }
                    if ((previous_config.lightness != config.lightness) ||
                            (previous_config.contrast != config.contrast)) {
                        caster_set_tone(config.lightness, config.contrast);
                    }
                    if ((previous_config.autoclear_mode != config.autoclear_mode) ||
                            (previous_config.autoclear_interval != config.autoclear_interval) ||
                            (previous_config.autoclear_threshold != config.autoclear_threshold)) {
                        reset_autoclear_state(&autoclear_timeout,
                                &autoclear_damage_counter,
                                &autoclear_damage_last);
                    }
                    if (previous_mode != (update_mode_t)config.update_mode) {
                        mode = mode_index_for((update_mode_t)config.update_mode);
                        caster_setmode(0, 0, config.hact, config.vact,
                                modes[mode].id);
                        reset_autoclear_state(&autoclear_timeout,
                                &autoclear_damage_counter,
                                &autoclear_damage_last);
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
                    &autoclear_timeout, &autoclear_damage_counter,
                    &autoclear_damage_last, &menu_render_state,
                    &autoclear_previous_mode, &tmds_mode);
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
