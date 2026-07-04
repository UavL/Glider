#include "fpga_spi_policy.h"

uint32_t fpga_spi_bitstream_hz(void) {
    return 24000000u;
}

uint32_t fpga_spi_register_hz(void) {
    return 1000000u;
}
