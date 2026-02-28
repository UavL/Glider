#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include "config.h"

int main(int argc, char *argv[]) {
    config_init();

    if (argc != 5) {
        printf("Usage: cfggen <size_in> <x_res> <y_res> <ref_hz>\n");
        return -1;
    }

    float size_in = atof(argv[1]);
    int x_res = atoi(argv[2]);
    int y_res = atoi(argv[3]);
    int ref_hz = atoi(argv[4]);

    // Calculate size
    float size_mm = size_in * 25.4f;
    float diag_res = sqrtf(powf(x_res, 2.f) + powf(y_res, 2.f));
    config.size_x_mm = roundf(size_mm / diag_res * x_res);
    config.size_y_mm = roundf(size_mm / diag_res * y_res);

    // Set year and week
    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    int week = (tm.tm_yday + 7 - (tm.tm_wday ? (tm.tm_wday - 1) : 6)) / 7;
    config.mfg_week = week;
    // tm_year starts from 1900, edid starts from 1990
    config.mfg_year = tm.tm_year - 90;

    // Calculate CVT RBv2
    config.hact = x_res;
    config.hblk = 80;
    config.hfp = 8;
    config.hsync = 32;

    config.vact = y_res;
    config.vsync = 8;
    // Calculate Vblank time, it needs to be >460us
    float act_lines_time = 1000.f / ref_hz - 0.46;
    config.vblk = (uint16_t)((float)(config.vact) / act_lines_time * 0.46f + 1.f);
    // VBP is fixed to 6 lines
    config.vfp = config.vblk - config.vsync - 6;

    // PCLK needs to be rounded to the nearest kHz
    config.pclk_hz = (uint32_t)roundf((config.hact + config.hblk) *
        (config.vact + config.vblk) * ref_hz / 1000.f) * 1000;

    config.tcon_hfp = 16;
    config.tcon_hsync = 2;
    config.tcon_hbp = 2;
    config.tcon_hact = x_res / 4;

    config.tcon_vsync = 1;
    config.tcon_vbp = 2;
    config.tcon_vfp = config.vblk - config.vfp - 1 - 2;
    config.tcon_vact = y_res;

    printf("Summary:\n");
    printf("Size X: %d\n", config.size_x_mm);
    printf("Size Y: %d\n", config.size_y_mm);
    printf("Mfg Year: %d\n", config.mfg_year + 1990);
    printf("Mfg Week: %d\n", config.mfg_week);

    printf("PCLK: %d Hz\n", config.pclk_hz);
    printf("HACT: %d\n", config.hact);
    printf("HBLK: %d\n", config.hblk);
    printf("HFP:  %d\n", config.hfp);
    printf("HSW:  %d\n", config.hsync);
    printf("VACT: %d\n", config.vact);
    printf("VBLK: %d\n", config.vblk);
    printf("VFP:  %d\n", config.vfp);
    printf("VSW:  %d\n", config.vsync);
    printf("TCON_HACT: %d\n", config.tcon_hact);
    printf("TCON_HFP:  %d\n", config.tcon_hfp);
    printf("TCON_HSW:  %d\n", config.tcon_hsync);
    printf("TCON_HBP:  %d\n", config.tcon_hbp);
    printf("TCON_VACT: %d\n", config.tcon_vact);
    printf("TCON_VFP:  %d\n", config.tcon_vfp);
    printf("TCON_VSW:  %d\n", config.tcon_vsync);
    printf("TCON_VBP:  %d\n", config.tcon_vbp);

    printf("Actual refresh rate: %.2f Hz\n", (float)(config.pclk_hz) /
        ((config.hact + config.hblk) * (config.vact + config.vblk)));

    FILE *fp;
    fp = fopen("config.bin", "wb");
    fwrite(&config, sizeof(config), 1, fp);
    fclose(fp);

    return 0;
}
