#include "osd_font.h"

const osd_font_t *osd_font_from_memory(const void *data, size_t size) {
    if ((data == NULL) || (size < sizeof(osd_font_header_t)))
        return NULL;

    const osd_font_t *font = (const osd_font_t *)data;
    const osd_font_header_t *h = &font->header;
    if (h->magic != OSD_FONT_MAGIC)
        return NULL;
    if (h->version != OSD_FONT_VERSION)
        return NULL;
    if (h->type != OSD_FONT_TYPE_PROPORTIONAL_ASCII)
        return NULL;
    if (h->pixfmt != OSD_FONT_PIXFMT_Y1)
        return NULL;
    if ((h->height == 0) || (h->chars == 0) || (h->glyph_words < 2))
        return NULL;
    if (((h->glyph_words - 1u) % h->height) != 0)
        return NULL;
    if (h->data_words != (h->chars * h->glyph_words))
        return NULL;

    size_t required = sizeof(osd_font_header_t) + ((size_t)h->data_words * sizeof(uint32_t));
    if (size < required)
        return NULL;

    return font;
}

const osd_font_glyph_t *osd_font_get_glyph(const osd_font_t *font, uint32_t ch) {
    if (font == NULL)
        return NULL;
    const osd_font_header_t *h = &font->header;
    if ((ch < h->offset) || (ch >= (h->offset + h->chars)))
        return NULL;

    uint32_t index = ch - h->offset;
    return (const osd_font_glyph_t *)&font->data[index * h->glyph_words];
}

uint32_t osd_font_text_width(const osd_font_t *font, const char *s, uint32_t max_chars) {
    uint32_t width = 0;
    uint32_t count = 0;

    if ((font == NULL) || (s == NULL))
        return 0;

    while ((*s != '\0') && (count < max_chars)) {
        const osd_font_glyph_t *glyph = osd_font_get_glyph(font, (uint8_t)*s);
        if (glyph != NULL)
            width += glyph->width;
        s++;
        count++;
    }

    return width;
}
