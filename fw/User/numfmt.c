#include "numfmt.h"

#include <stdint.h>
#include <stdio.h>

static int is_space(char ch) {
    return (ch == ' ') || (ch == '\t') || (ch == '\r') || (ch == '\n');
}

static int is_digit(char ch) {
    return (ch >= '0') && (ch <= '9');
}

bool numfmt_parse_float(const char *text, float *value) {
    if ((text == NULL) || (value == NULL))
        return false;

    while (is_space(*text))
        text++;

    int sign = 1;
    if ((*text == '-') || (*text == '+')) {
        if (*text == '-')
            sign = -1;
        text++;
    }

    uint32_t whole = 0;
    uint32_t frac = 0;
    uint32_t divisor = 1;
    int digits = 0;

    while (is_digit(*text)) {
        whole = whole * 10u + (uint32_t)(*text - '0');
        text++;
        digits++;
    }

    if (*text == '.') {
        text++;
        while (is_digit(*text)) {
            if (divisor < 1000000u) {
                frac = frac * 10u + (uint32_t)(*text - '0');
                divisor *= 10u;
            }
            text++;
            digits++;
        }
    }

    while (is_space(*text))
        text++;

    if ((digits == 0) || (*text != '\0'))
        return false;

    float parsed = (float)whole;
    if (divisor > 1u)
        parsed += (float)frac / (float)divisor;
    *value = (sign < 0) ? -parsed : parsed;
    return true;
}

void numfmt_format_fixed(char *buf, size_t len, float value, unsigned decimals) {
    static const uint32_t scales[] = {1u, 10u, 100u, 1000u};

    if ((buf == NULL) || (len == 0))
        return;

    if (decimals >= (sizeof(scales) / sizeof(scales[0])))
        decimals = (sizeof(scales) / sizeof(scales[0])) - 1u;

    uint32_t scale = scales[decimals];
    float scaled_f = value * (float)scale;
    int32_t scaled = (int32_t)(scaled_f + ((scaled_f >= 0.0f) ? 0.5f : -0.5f));

    if (scaled == 0) {
        snprintf(buf, len, (decimals == 0) ? "0" : "0.%0*u",
                (int)decimals, 0u);
        return;
    }

    int negative = scaled < 0;
    uint32_t mag = negative ? (uint32_t)(-scaled) : (uint32_t)scaled;
    uint32_t whole = mag / scale;
    uint32_t frac = mag % scale;

    if (decimals == 0) {
        snprintf(buf, len, "%s%u", negative ? "-" : "", (unsigned)whole);
    }
    else {
        snprintf(buf, len, "%s%u.%0*u", negative ? "-" : "",
                (unsigned)whole, (int)decimals, (unsigned)frac);
    }
}
