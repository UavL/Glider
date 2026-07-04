#include <stdint.h>
#include <stdio.h>

#include "fpga_spi_policy.h"

#define ASSERT_EQ(expected, actual) do { \
    if ((expected) != (actual)) { \
        printf("ASSERT_EQ failed at %s:%d: expected %lu got %lu\n", \
                __FILE__, __LINE__, (unsigned long)(expected), \
                (unsigned long)(actual)); \
        return 1; \
    } \
} while (0)

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("ASSERT_TRUE failed at %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return 1; \
    } \
} while (0)

static int test_bitstream_load_uses_fast_spi(void) {
    ASSERT_EQ(24000000u, fpga_spi_bitstream_hz());
    ASSERT_EQ(1000000u, fpga_spi_register_hz());
    ASSERT_TRUE(fpga_spi_bitstream_hz() > fpga_spi_register_hz());

    return 0;
}

int main(void) {
    int rc = 0;

    rc |= test_bitstream_load_uses_fast_spi();

    return rc;
}
