#include <stdint.h>
#include <stdio.h>

#include "osd_font.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_EQ(expected, actual) do { \
    unsigned long long exp__ = (unsigned long long)(expected); \
    unsigned long long act__ = (unsigned long long)(actual); \
    if (exp__ != act__) { \
        printf("ASSERT_EQ failed at %s:%d: expected %llu got %llu\n", \
                __FILE__, __LINE__, exp__, act__); \
        return 1; \
    } \
} while (0)

typedef struct {
    osd_font_header_t header;
    uint32_t glyphs[2 * 3];
} tiny_font_blob_t;

static const tiny_font_blob_t tiny_font = {
    .header = {
        .magic = OSD_FONT_MAGIC,
        .version = OSD_FONT_VERSION,
        .type = OSD_FONT_TYPE_PROPORTIONAL_ASCII,
        .pixfmt = OSD_FONT_PIXFMT_Y1,
        .height = 2,
        .offset = 65,
        .chars = 2,
        .glyph_words = 3,
        .data_words = 6,
    },
    .glyphs = {
        3, 0xE0000000u, 0xA0000000u,
        5, 0xF8000000u, 0x88000000u,
    },
};

static int test_font_validation_and_metrics(void) {
    const osd_font_t *font = osd_font_from_memory(&tiny_font, sizeof(tiny_font));

    ASSERT_TRUE(font != NULL);
    ASSERT_EQ(8, osd_font_text_width(font, "AB", 2));
    ASSERT_EQ(3, osd_font_text_width(font, "AZ", 2));
    ASSERT_EQ(0, osd_font_text_width(font, "Z", 1));

    return 0;
}

static int test_font_validation_rejects_bad_magic(void) {
    tiny_font_blob_t bad = tiny_font;

    bad.header.magic = 0x12345678u;
    ASSERT_TRUE(osd_font_from_memory(&bad, sizeof(bad)) == NULL);

    return 0;
}

static int test_glyph_access_bounds(void) {
    const osd_font_t *font = osd_font_from_memory(&tiny_font, sizeof(tiny_font));
    const osd_font_glyph_t *glyph_a = osd_font_get_glyph(font, 'A');

    ASSERT_TRUE(glyph_a != NULL);
    ASSERT_EQ(3, glyph_a->width);
    ASSERT_TRUE(osd_font_get_glyph(font, 'Z') == NULL);

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_font_validation_and_metrics();
    rc |= test_font_validation_rejects_bad_magic();
    rc |= test_glyph_access_bounds();

    return rc;
}
