#pragma once

#include "config.h"

typedef enum {
    UI_MENU_DEPTH_CATEGORIES = 0,
    UI_MENU_DEPTH_ITEMS,
    UI_MENU_DEPTH_MODAL,
} ui_menu_depth_t;

typedef enum {
    UI_MENU_EVENT_PREV = 0,
    UI_MENU_EVENT_NEXT,
    UI_MENU_EVENT_ENTER,
    UI_MENU_EVENT_BACK,
} ui_menu_event_t;

typedef struct {
    config_t *config;
    int category_index;
    int item_index;
    int modal_index;
    int draft_value;
    ui_menu_depth_t depth;
} ui_menu_t;

void ui_menu_init(ui_menu_t *menu, config_t *cfg);
void ui_menu_handle(ui_menu_t *menu, ui_menu_event_t event);
ui_menu_depth_t ui_menu_depth(const ui_menu_t *menu);
const char *ui_menu_category_label(const ui_menu_t *menu);
const char *ui_menu_selected_label(const ui_menu_t *menu);
const char *ui_menu_selected_value_label(const ui_menu_t *menu);
const char *ui_menu_modal_value_label(const ui_menu_t *menu);
int ui_menu_modal_is_scalar(const ui_menu_t *menu);
int ui_menu_modal_count(const ui_menu_t *menu);
int ui_menu_modal_index(const ui_menu_t *menu);
int ui_menu_row_count(const ui_menu_t *menu);
const char *ui_menu_row_label(const ui_menu_t *menu, int row);
const char *ui_menu_row_value(const ui_menu_t *menu, int row);
int ui_menu_row_selected(const ui_menu_t *menu, int row);
int ui_menu_viewport_first(int current_first, int selected, int row_count, int visible_rows);
