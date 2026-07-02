#include <stddef.h>

#include "ui_menu.h"

typedef enum {
    MENU_ITEM_UPDATE_MODE = 0,
    MENU_ITEM_LIGHTNESS,
    MENU_ITEM_CONTRAST,
    MENU_ITEM_SATURATION,
    MENU_ITEM_AUTO_CLEAR,
    MENU_ITEM_AUTO_CLEAR_INTERVAL,
    MENU_ITEM_AUTO_CLEAR_THRESHOLD,
    MENU_ITEM_BUTTON_1_SHORT,
    MENU_ITEM_BUTTON_2_SHORT,
    MENU_ITEM_BUTTON_3_SHORT,
    MENU_ITEM_BUTTON_1_LONG,
    MENU_ITEM_BUTTON_2_LONG,
    MENU_ITEM_BUTTON_3_LONG,
    MENU_ITEM_INPUT,
    MENU_ITEM_COUNT,
} menu_item_id_t;

typedef struct {
    menu_item_id_t id;
    const char *label;
} menu_item_t;

typedef struct {
    const char *label;
    const menu_item_t *items;
    int item_count;
} menu_category_t;

typedef struct {
    int value;
    const char *label;
} value_label_t;

static const menu_item_t display_items[] = {
    {MENU_ITEM_UPDATE_MODE, "Update Mode"},
    {MENU_ITEM_LIGHTNESS, "Lightness"},
    {MENU_ITEM_CONTRAST, "Contrast"},
    {MENU_ITEM_SATURATION, "Saturation"},
    {MENU_ITEM_AUTO_CLEAR, "Auto Clear"},
    {MENU_ITEM_AUTO_CLEAR_INTERVAL, "Clear Interval"},
    {MENU_ITEM_AUTO_CLEAR_THRESHOLD, "Clear Threshold"},
};

static const menu_item_t button_items[] = {
    {MENU_ITEM_BUTTON_1_SHORT, "Button 1 Short"},
    {MENU_ITEM_BUTTON_2_SHORT, "Button 2 Short"},
    {MENU_ITEM_BUTTON_3_SHORT, "Button 3 Short"},
    {MENU_ITEM_BUTTON_1_LONG, "Button 1 Long"},
    {MENU_ITEM_BUTTON_2_LONG, "Button 2 Long"},
    {MENU_ITEM_BUTTON_3_LONG, "Button 3 Long"},
};

static const menu_item_t system_items[] = {
    {MENU_ITEM_INPUT, "Input"},
};

static const menu_category_t categories[] = {
    {"Display", display_items, (int)(sizeof(display_items) / sizeof(display_items[0]))},
    {"Buttons", button_items, (int)(sizeof(button_items) / sizeof(button_items[0]))},
    {"System", system_items, (int)(sizeof(system_items) / sizeof(system_items[0]))},
};

static const value_label_t update_mode_values[] = {
    {UM_FAST_MONO_BAYER, "Browsing"},
    {UM_FAST_MONO_BLUE_NOISE, "Watching"},
    {UM_FAST_GREY, "Typing"},
    {UM_AUTO_LUT_NO_DITHER, "Reading"},
};

static const value_label_t autoclear_mode_values[] = {
    {AC_OFF, "Off"},
    {AC_ADAPT, "Adaptive"},
    {AC_FIXED, "Fixed"},
};

static const value_label_t autoclear_interval_values[] = {
    {AC_1MIN, "1 min"},
    {AC_5MIN, "5 min"},
    {AC_15MIN, "15 min"},
};

static const value_label_t autoclear_threshold_values[] = {
    {AC_THRES_HIGH, "High"},
    {AC_THRES_MED, "Medium"},
    {AC_THRES_LOW, "Low"},
};

static const value_label_t input_values[] = {
    {INPUT_SEL_AUTO, "Auto"},
    {INPUT_SEL_TMDS, "TMDS"},
    {INPUT_SEL_DP, "DP"},
};

static const value_label_t scalar_values[] = {
    {-3, "-3"},
    {-2, "-2"},
    {-1, "-1"},
    {0, "0"},
    {1, "1"},
    {2, "2"},
    {3, "3"},
};

static const value_label_t action_values[] = {
    {ACT_PREV_MODE, "Previous Display Mode"},
    {ACT_NEXT_MODE, "Next Display Mode"},
    {ACT_MODE_BROWSING, "Set Mode to Browsing"},
    {ACT_MODE_WATCHING, "Set Mode to Watching"},
    {ACT_MODE_TYPING, "Set Mode to Typing"},
    {ACT_MODE_READING, "Set Mode to Reading"},
    {ACT_CLEAR, "Clear Screen"},
    {ACT_TOGGLE_AC, "Toggle Auto Clear"},
    {ACT_OPEN_SETTINGS, "Open Settings"},
    {ACT_POFF, "Power Off"},
    {ACT_INPUT_AUTO, "Input Auto"},
    {ACT_INPUT_TMDS, "Input TMDS"},
    {ACT_INPUT_DP, "Input DP"},
};

static char number_value_buf[8];

static int wrap_index(int index, int count) {
    if (count <= 0)
        return 0;
    if (index < 0)
        return count - 1;
    if (index >= count)
        return 0;
    return index;
}

static const menu_item_t *selected_item(const ui_menu_t *menu) {
    if ((menu == NULL) || (menu->depth == UI_MENU_DEPTH_CATEGORIES))
        return NULL;
    const menu_category_t *category = &categories[menu->category_index];
    return &category->items[menu->item_index];
}

static int value_to_index(const value_label_t *values, int count, int value) {
    for (int i = 0; i < count; i++) {
        if (values[i].value == value)
            return i;
    }
    return 0;
}

static const char *value_label(const value_label_t *values, int count, int value) {
    return values[value_to_index(values, count, value)].label;
}

static int modal_count(const ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if (item == NULL)
        return 0;

    if (item->id == MENU_ITEM_UPDATE_MODE)
        return (int)(sizeof(update_mode_values) / sizeof(update_mode_values[0]));
    if ((item->id == MENU_ITEM_LIGHTNESS) ||
            (item->id == MENU_ITEM_CONTRAST) ||
            (item->id == MENU_ITEM_SATURATION))
        return (int)(sizeof(scalar_values) / sizeof(scalar_values[0]));
    if ((item->id >= MENU_ITEM_BUTTON_1_SHORT) && (item->id <= MENU_ITEM_BUTTON_3_LONG))
        return (int)(sizeof(action_values) / sizeof(action_values[0]));
    if (item->id == MENU_ITEM_AUTO_CLEAR)
        return (int)(sizeof(autoclear_mode_values) / sizeof(autoclear_mode_values[0]));
    if (item->id == MENU_ITEM_AUTO_CLEAR_INTERVAL)
        return (int)(sizeof(autoclear_interval_values) / sizeof(autoclear_interval_values[0]));
    if (item->id == MENU_ITEM_AUTO_CLEAR_THRESHOLD)
        return (int)(sizeof(autoclear_threshold_values) / sizeof(autoclear_threshold_values[0]));
    if (item->id == MENU_ITEM_INPUT)
        return (int)(sizeof(input_values) / sizeof(input_values[0]));

    return 0;
}

static int item_is_scalar(menu_item_id_t id) {
    return (id == MENU_ITEM_LIGHTNESS) ||
            (id == MENU_ITEM_CONTRAST) ||
            (id == MENU_ITEM_SATURATION);
}

static int *config_value_ptr(ui_menu_t *menu, menu_item_id_t id) {
    switch (id) {
    case MENU_ITEM_UPDATE_MODE:
        return &menu->config->update_mode;
    case MENU_ITEM_LIGHTNESS:
        return &menu->config->lightness;
    case MENU_ITEM_CONTRAST:
        return &menu->config->contrast;
    case MENU_ITEM_SATURATION:
        return &menu->config->saturation;
    case MENU_ITEM_AUTO_CLEAR:
        return &menu->config->autoclear_mode;
    case MENU_ITEM_AUTO_CLEAR_INTERVAL:
        return &menu->config->autoclear_interval;
    case MENU_ITEM_AUTO_CLEAR_THRESHOLD:
        return &menu->config->autoclear_threshold;
    case MENU_ITEM_BUTTON_1_SHORT:
    case MENU_ITEM_BUTTON_2_SHORT:
    case MENU_ITEM_BUTTON_3_SHORT:
    case MENU_ITEM_BUTTON_1_LONG:
    case MENU_ITEM_BUTTON_2_LONG:
    case MENU_ITEM_BUTTON_3_LONG:
        return &menu->config->button_actions[id - MENU_ITEM_BUTTON_1_SHORT];
    case MENU_ITEM_INPUT:
        return NULL;
    default:
        return NULL;
    }
}

static int get_config_value(const ui_menu_t *menu, menu_item_id_t id) {
    int *ptr = config_value_ptr((ui_menu_t *)menu, id);
    if (ptr != NULL)
        return *ptr;
    if (id == MENU_ITEM_INPUT)
        return menu->config->input_sel;
    return 0;
}

static void set_config_value(ui_menu_t *menu, menu_item_id_t id, int value) {
    int *ptr = config_value_ptr(menu, id);
    if (ptr != NULL) {
        *ptr = value;
        return;
    }
    if (id == MENU_ITEM_INPUT)
        menu->config->input_sel = (uint8_t)value;
}

static const value_label_t *item_values(menu_item_id_t id, int *count) {
    if (id == MENU_ITEM_UPDATE_MODE) {
        *count = (int)(sizeof(update_mode_values) / sizeof(update_mode_values[0]));
        return update_mode_values;
    }
    if ((id == MENU_ITEM_LIGHTNESS) ||
            (id == MENU_ITEM_CONTRAST) ||
            (id == MENU_ITEM_SATURATION)) {
        *count = (int)(sizeof(scalar_values) / sizeof(scalar_values[0]));
        return scalar_values;
    }
    if ((id >= MENU_ITEM_BUTTON_1_SHORT) && (id <= MENU_ITEM_BUTTON_3_LONG)) {
        *count = (int)(sizeof(action_values) / sizeof(action_values[0]));
        return action_values;
    }
    if (id == MENU_ITEM_AUTO_CLEAR) {
        *count = (int)(sizeof(autoclear_mode_values) / sizeof(autoclear_mode_values[0]));
        return autoclear_mode_values;
    }
    if (id == MENU_ITEM_AUTO_CLEAR_INTERVAL) {
        *count = (int)(sizeof(autoclear_interval_values) / sizeof(autoclear_interval_values[0]));
        return autoclear_interval_values;
    }
    if (id == MENU_ITEM_AUTO_CLEAR_THRESHOLD) {
        *count = (int)(sizeof(autoclear_threshold_values) / sizeof(autoclear_threshold_values[0]));
        return autoclear_threshold_values;
    }
    if (id == MENU_ITEM_INPUT) {
        *count = (int)(sizeof(input_values) / sizeof(input_values[0]));
        return input_values;
    }

    *count = 0;
    return NULL;
}

static void open_modal(ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if (item == NULL)
        return;

    int count = 0;
    const value_label_t *values = item_values(item->id, &count);
    if (values != NULL) {
        menu->draft_value = get_config_value(menu, item->id);
        menu->modal_index = value_to_index(values, count, menu->draft_value);
        menu->depth = UI_MENU_DEPTH_MODAL;
    }
}

static void commit_modal(ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if (item == NULL)
        return;

    int count = 0;
    const value_label_t *values = item_values(item->id, &count);
    if ((values != NULL) && (menu->modal_index < count))
        set_config_value(menu, item->id, values[menu->modal_index].value);
}

void ui_menu_init(ui_menu_t *menu, config_t *cfg) {
    menu->config = cfg;
    menu->category_index = 0;
    menu->item_index = 0;
    menu->modal_index = 0;
    menu->draft_value = 0;
    menu->depth = UI_MENU_DEPTH_CATEGORIES;
}

void ui_menu_handle(ui_menu_t *menu, ui_menu_event_t event) {
    if (menu == NULL)
        return;

    if (menu->depth == UI_MENU_DEPTH_CATEGORIES) {
        if (event == UI_MENU_EVENT_PREV)
            menu->category_index = wrap_index(menu->category_index - 1,
                    (int)(sizeof(categories) / sizeof(categories[0])));
        else if (event == UI_MENU_EVENT_NEXT)
            menu->category_index = wrap_index(menu->category_index + 1,
                    (int)(sizeof(categories) / sizeof(categories[0])));
        else if (event == UI_MENU_EVENT_ENTER) {
            menu->item_index = 0;
            menu->depth = UI_MENU_DEPTH_ITEMS;
        }
        return;
    }

    if (menu->depth == UI_MENU_DEPTH_ITEMS) {
        const menu_category_t *category = &categories[menu->category_index];
        if (event == UI_MENU_EVENT_PREV)
            menu->item_index = wrap_index(menu->item_index - 1, category->item_count);
        else if (event == UI_MENU_EVENT_NEXT)
            menu->item_index = wrap_index(menu->item_index + 1, category->item_count);
        else if (event == UI_MENU_EVENT_BACK)
            menu->depth = UI_MENU_DEPTH_CATEGORIES;
        else if (event == UI_MENU_EVENT_ENTER)
            open_modal(menu);
        return;
    }

    if (menu->depth == UI_MENU_DEPTH_MODAL) {
        int count = modal_count(menu);
        if (event == UI_MENU_EVENT_PREV)
            menu->modal_index = wrap_index(menu->modal_index - 1, count);
        else if (event == UI_MENU_EVENT_NEXT)
            menu->modal_index = wrap_index(menu->modal_index + 1, count);
        else if (event == UI_MENU_EVENT_BACK)
            menu->depth = UI_MENU_DEPTH_ITEMS;
        else if (event == UI_MENU_EVENT_ENTER) {
            commit_modal(menu);
            menu->depth = UI_MENU_DEPTH_ITEMS;
        }
    }
}

ui_menu_depth_t ui_menu_depth(const ui_menu_t *menu) {
    return menu->depth;
}

const char *ui_menu_category_label(const ui_menu_t *menu) {
    if (menu == NULL)
        return NULL;
    return categories[menu->category_index].label;
}

const char *ui_menu_selected_label(const ui_menu_t *menu) {
    if (menu == NULL)
        return NULL;
    if (menu->depth == UI_MENU_DEPTH_CATEGORIES)
        return categories[menu->category_index].label;

    const menu_item_t *item = selected_item(menu);
    return (item != NULL) ? item->label : NULL;
}

const char *ui_menu_selected_value_label(const ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if (item == NULL)
        return NULL;

    return ui_menu_row_value(menu, menu->item_index);
}

static const char *scalar_label(int value) {
    if (value < 0) {
        number_value_buf[0] = '-';
        number_value_buf[1] = (char)('0' + (-value));
        number_value_buf[2] = '\0';
    }
    else {
        number_value_buf[0] = (char)('0' + value);
        number_value_buf[1] = '\0';
    }
    return number_value_buf;
}

int ui_menu_row_count(const ui_menu_t *menu) {
    if (menu == NULL)
        return 0;
    if (menu->depth == UI_MENU_DEPTH_CATEGORIES)
        return (int)(sizeof(categories) / sizeof(categories[0]));
    if (menu->depth == UI_MENU_DEPTH_ITEMS)
        return categories[menu->category_index].item_count;
    return modal_count(menu);
}

const char *ui_menu_row_label(const ui_menu_t *menu, int row) {
    if ((menu == NULL) || (row < 0) || (row >= ui_menu_row_count(menu)))
        return NULL;

    if (menu->depth == UI_MENU_DEPTH_CATEGORIES)
        return categories[row].label;
    if (menu->depth == UI_MENU_DEPTH_ITEMS)
        return categories[menu->category_index].items[row].label;

    const menu_item_t *item = selected_item(menu);
    int count = 0;
    const value_label_t *values = item_values(item->id, &count);
    if ((values != NULL) && (row < count))
        return values[row].label;

    return NULL;
}

const char *ui_menu_row_value(const ui_menu_t *menu, int row) {
    if ((menu == NULL) || (row < 0) || (row >= ui_menu_row_count(menu)))
        return NULL;
    if (menu->depth != UI_MENU_DEPTH_ITEMS)
        return "";

    const menu_item_t *item = &categories[menu->category_index].items[row];
    if ((item->id == MENU_ITEM_LIGHTNESS) ||
            (item->id == MENU_ITEM_CONTRAST) ||
            (item->id == MENU_ITEM_SATURATION)) {
        int *value = config_value_ptr((ui_menu_t *)menu, item->id);
        return scalar_label((value != NULL) ? *value : 0);
    }

    int count = 0;
    const value_label_t *values = item_values(item->id, &count);
    if (values != NULL)
        return value_label(values, count, get_config_value(menu, item->id));

    return "";
}

int ui_menu_row_selected(const ui_menu_t *menu, int row) {
    if ((menu == NULL) || (row < 0) || (row >= ui_menu_row_count(menu)))
        return 0;
    if (menu->depth == UI_MENU_DEPTH_CATEGORIES)
        return row == menu->category_index;
    if (menu->depth == UI_MENU_DEPTH_ITEMS)
        return row == menu->item_index;
    return row == menu->modal_index;
}

const char *ui_menu_modal_value_label(const ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if ((item == NULL) || (menu->depth != UI_MENU_DEPTH_MODAL))
        return NULL;

    int count = 0;
    const value_label_t *values = item_values(item->id, &count);
    if ((values != NULL) && (menu->modal_index < count))
        return values[menu->modal_index].label;

    return NULL;
}

int ui_menu_modal_is_scalar(const ui_menu_t *menu) {
    const menu_item_t *item = selected_item(menu);
    if ((item == NULL) || (menu->depth != UI_MENU_DEPTH_MODAL))
        return 0;
    return item_is_scalar(item->id);
}

int ui_menu_modal_count(const ui_menu_t *menu) {
    if ((menu == NULL) || (menu->depth != UI_MENU_DEPTH_MODAL))
        return 0;
    return modal_count(menu);
}

int ui_menu_modal_index(const ui_menu_t *menu) {
    if ((menu == NULL) || (menu->depth != UI_MENU_DEPTH_MODAL))
        return 0;
    return menu->modal_index;
}

int ui_menu_viewport_first(int current_first, int selected, int row_count, int visible_rows) {
    int max_first;

    if ((row_count <= 0) || (visible_rows <= 0))
        return 0;
    if (visible_rows >= row_count)
        return 0;

    max_first = row_count - visible_rows;
    if (current_first < 0)
        current_first = 0;
    if (current_first > max_first)
        current_first = max_first;

    if (selected < 0)
        selected = 0;
    if (selected >= row_count)
        selected = row_count - 1;

    if (selected < current_first)
        return selected;
    if (selected >= current_first + visible_rows)
        return selected - visible_rows + 1;
    return current_first;
}
