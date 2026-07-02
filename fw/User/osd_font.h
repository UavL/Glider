#pragma once

#include <stddef.h>
#include <stdint.h>

#define OSD_FONT_MAGIC   0x46534f47u
#define OSD_FONT_VERSION 1u

typedef enum {
    OSD_FONT_TYPE_PROPORTIONAL_ASCII = 1,
} osd_font_type_t;

typedef enum {
    OSD_FONT_PIXFMT_Y1 = 1,
} osd_font_pixfmt_t;

typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t type;
    uint32_t pixfmt;
    uint32_t height;
    uint32_t offset;
    uint32_t chars;
    uint32_t glyph_words;
    uint32_t data_words;
} osd_font_header_t;

typedef struct {
    osd_font_header_t header;
    uint32_t data[];
} osd_font_t;

typedef struct {
    uint32_t width;
    uint32_t rows[];
} osd_font_glyph_t;

const osd_font_t *osd_font_from_memory(const void *data, size_t size);
const osd_font_glyph_t *osd_font_get_glyph(const osd_font_t *font, uint32_t ch);
uint32_t osd_font_text_width(const osd_font_t *font, const char *s, uint32_t max_chars);
