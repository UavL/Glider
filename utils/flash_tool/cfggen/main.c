#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <time.h>
#include <string.h>
#include "config.h"

typedef enum {
    TIMING_CVT_RB2,
    TIMING_CVT_RB,
} timing_standard_t;

static const char *timing_standard_name(timing_standard_t standard) {
    switch (standard) {
    case TIMING_CVT_RB2:
        return "CVT-RBv2";
    case TIMING_CVT_RB:
        return "CVT-RB";
    default:
        return "unknown";
    }
}

static int cvt_vsync_width(int x_res, int y_res) {
    if (x_res * 3 == y_res * 4)
        return 4;
    if (x_res * 9 == y_res * 16)
        return 5;
    if (x_res * 10 == y_res * 16)
        return 6;
    if (x_res * 4 == y_res * 5)
        return 7;
    if (x_res * 9 == y_res * 15)
        return 7;
    return 10;
}

static uint32_t round_clock(float raw_hz, uint32_t granularity_hz) {
    return (uint32_t)roundf(raw_hz / (float)granularity_hz) * granularity_hz;
}

int main(int argc, char *argv[]) {
    config_init();

    if ((argc < 5) || (argc > 8)) {
        printf("Usage: cfggen <size_in> <x_res> <y_res> <ref_hz> [cvt-rb2|cvt-rb] [--out <file>]\n");
        return -1;
    }

    float size_in = atof(argv[1]);
    int x_res = atoi(argv[2]);
    int y_res = atoi(argv[3]);
    int ref_hz = atoi(argv[4]);
    timing_standard_t timing_standard = TIMING_CVT_RB2;
    const char *output_path = "config.bin";

    int argi = 5;
    if ((argi < argc) && (strcmp(argv[argi], "--out") != 0)) {
        if (strcmp(argv[argi], "cvt-rb2") == 0) {
            timing_standard = TIMING_CVT_RB2;
        }
        else if (strcmp(argv[argi], "cvt-rb") == 0) {
            timing_standard = TIMING_CVT_RB;
        }
        else {
            printf("Unknown timing standard: %s\n", argv[argi]);
            printf("Usage: cfggen <size_in> <x_res> <y_res> <ref_hz> [cvt-rb2|cvt-rb] [--out <file>]\n");
            return -1;
        }
        argi++;
    }

    if (argi < argc) {
        if ((strcmp(argv[argi], "--out") != 0) || ((argi + 1) >= argc)) {
            printf("Usage: cfggen <size_in> <x_res> <y_res> <ref_hz> [cvt-rb2|cvt-rb] [--out <file>]\n");
            return -1;
        }
        output_path = argv[argi + 1];
        argi += 2;
    }
    if (argi != argc) {
        printf("Usage: cfggen <size_in> <x_res> <y_res> <ref_hz> [cvt-rb2|cvt-rb] [--out <file>]\n");
        return -1;
    }

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

    // Calculate CVT reduced blanking host timings.
    config.hact = x_res;
    if (timing_standard == TIMING_CVT_RB2) {
        config.hblk = 80;
        config.hfp = 8;
        config.hsync = 32;
    }
    else {
        config.hblk = 160;
        config.hfp = 48;
        config.hsync = 32;
    }

    config.vact = y_res;
    if (timing_standard == TIMING_CVT_RB2) {
        config.vsync = 8;
    }
    else {
        config.vsync = cvt_vsync_width(x_res, y_res);
    }
    // Calculate Vblank time, it needs to be >460us
    float act_lines_time = 1000.f / ref_hz - 0.46;
    config.vblk = (uint16_t)((float)(config.vact) / act_lines_time * 0.46f + 1.f);
    if (timing_standard == TIMING_CVT_RB2) {
        // VBP is fixed to 6 lines
        config.vfp = config.vblk - config.vsync - 6;
    }
    else {
        config.vfp = 3;
        uint16_t min_vblk = config.vfp + config.vsync + 6;
        if (config.vblk < min_vblk)
            config.vblk = min_vblk;
    }

    float raw_pclk_hz = (config.hact + config.hblk) *
        (config.vact + config.vblk) * ref_hz;
    if (timing_standard == TIMING_CVT_RB2) {
        // RBv2 pixel clock is rounded to the nearest kHz.
        config.pclk_hz = round_clock(raw_pclk_hz, 1000);
    }
    else {
        // RBv1 pixel clock is rounded to the nearest 0.25 MHz.
        config.pclk_hz = round_clock(raw_pclk_hz, 250000);
    }

    config.tcon_hsync = 2;
    config.tcon_hbp = 2;
    config.tcon_hfp = config.hblk / 4 - config.tcon_hsync - config.tcon_hbp;
    config.tcon_hact = x_res / 4;

    config.tcon_vsync = 1;
    config.tcon_vbp = 2;
    config.tcon_vfp = config.vblk - config.vfp - 1 - 2;
    config.tcon_vact = y_res;

    printf("Summary:\n");
    printf("Timing standard: %s\n", timing_standard_name(timing_standard));
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
    printf("Output: %s\n", output_path);

    fp = fopen(output_path, "wb");
    if (fp == NULL) {
        printf("Unable to open output file: %s\n", output_path);
        return -1;
    }
    fwrite(&config, sizeof(config), 1, fp);
    fclose(fp);

    return 0;
}
