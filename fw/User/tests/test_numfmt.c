#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "numfmt.h"

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

#define ASSERT_FALSE(expr) ASSERT_TRUE(!(expr))

#define ASSERT_STR_EQ(expected, actual) do { \
    if (strcmp((expected), (actual)) != 0) { \
        printf("ASSERT_STR_EQ failed at %s:%d: expected '%s' got '%s'\n", \
                __FILE__, __LINE__, (expected), (actual)); \
        return 1; \
    } \
} while (0)

static int test_fixed_format_rounds_signed_values(void) {
    char buf[16];

    numfmt_format_fixed(buf, sizeof(buf), 12.345f, 2);
    ASSERT_STR_EQ("12.35", buf);

    numfmt_format_fixed(buf, sizeof(buf), -2.304f, 2);
    ASSERT_STR_EQ("-2.30", buf);

    numfmt_format_fixed(buf, sizeof(buf), -0.004f, 2);
    ASSERT_STR_EQ("0.00", buf);

    numfmt_format_fixed(buf, sizeof(buf), 99.95f, 1);
    ASSERT_STR_EQ("100.0", buf);

    numfmt_format_fixed(buf, sizeof(buf), 42.4f, 0);
    ASSERT_STR_EQ("42", buf);

    return 0;
}

static int test_fixed_parse_accepts_decimal_values(void) {
    float value = 0.0f;

    ASSERT_TRUE(numfmt_parse_float(" -2.30 ", &value));
    ASSERT_TRUE(value < -2.29f && value > -2.31f);

    ASSERT_TRUE(numfmt_parse_float("25", &value));
    ASSERT_TRUE(value < 25.01f && value > 24.99f);

    ASSERT_TRUE(numfmt_parse_float(".75", &value));
    ASSERT_TRUE(value < 0.76f && value > 0.74f);

    ASSERT_FALSE(numfmt_parse_float("", &value));
    ASSERT_FALSE(numfmt_parse_float("12x", &value));
    ASSERT_FALSE(numfmt_parse_float(".", &value));

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_fixed_format_rounds_signed_values();
    rc |= test_fixed_parse_accepts_decimal_values();

    return rc;
}
