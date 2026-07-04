#pragma once

#include <stdbool.h>
#include <stddef.h>

bool numfmt_parse_float(const char *text, float *value);
void numfmt_format_fixed(char *buf, size_t len, float value, unsigned decimals);
