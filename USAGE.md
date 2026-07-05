# Glider Usage

This guide covers the practical board workflow: first power-on, flashing an existing release, stock firmware behavior, display configuration, and then building from source. The main README keeps the deeper background on EPDs, Caster, and hardware design.

## Contents

- [First Use](#first-use)
- [Flashing Requirements](#flashing-requirements)
- [Flashing A Release Package](#flashing-a-release-package)
- [Stock Firmware Features](#stock-firmware-features)
- [Display Configuration](#display-configuration)
- [Building](#building)
- [Development Builds](#development-builds)
- [Manual Flashing](#manual-flashing)
- [Troubleshooting](#troubleshooting)

## First Use

Glider devkits ship with the screen and adapter already connected. Before powering the board, confirm the screen FPC, adapter board, and board-to-adapter connectors are firmly seated.

If you are using USB-C for both video and power, a single USB-C cable to a supported DisplayPort Alt Mode source, such as a laptop, is enough. If you are using an ARM Mac, install StillColor to disable FRC dithering; otherwise the host may continuously dither pixels and make the EPD update more often than intended. If DVI via the Mini-HDMI connector is needed, use two cables: USB-C for power and USB, plus a Mini-HDMI video cable for video.

The board ships with firmware pre-installed. On first power-on it should generally start working and display the active video input. The shipped firmware may still be outdated or buggy, so update the firmware even if first power-on appears to work. If first power-on does not work, update the firmware before debugging deeper.

## Flashing Requirements

Download a release zip from the GitLab release page. Inside the zip, there is a flash_tool directory. Flashing an existing release needs only:

- Python 3.
- Python `hidapi`: `pip3 install hidapi`.
- `dfu-util`.

Linux and macOS are the easiest supported flashing hosts. Windows is possible, but you need to locate a working `dfu-util` build yourself, and WinUSB driver installation via Zadig may be required before `dfu-util` can access the STM32 DFU interface.

Build tools are separate and much larger downloads. Install them only if you plan to build firmware or FPGA bitstreams from source.

## Flashing A Release Package

After downloading and extracting a release zip from the GitLab release page, open the `flash_tool` directory inside the zip. It contains:

- `glider_ec_rtos.bin`: MCU firmware.
- `fpga-8bit-mono.bit`, `fpga-8bit-k3.bit`, `fpga-16bit-mono.bit`, `fpga-16bit-k3.bit`: FPGA bitstreams.
- `fonts/`: OSD font files.
- `configs/config-6in.bin` and `configs/config-13in.bin`: display configs.
- `flash.py`: command-line flashing tool.

Enter DFU mode before starting the release flash: hold the button closer to the USB port while plugging in USB.

From the release `flash_tool` directory:

```bash
python3 flash.py
```

The tool runs `dfu-util` for the MCU firmware, warns if DFU flashing fails, prompts for the FPGA bitstream when multiple `fpga-*.bit` files exist, transfers bundled fonts, and asks whether to flash a display config. For the bundled monochrome kits, `fpga-8bit-mono.bit` is the normal bitstream choice. The config prompt defaults to yes; select `config-6in.bin` for the 6 inch kit or `config-13in.bin` for the 13.3 inch kit.

After flashing finishes, unplug and reconnect the board normally.

## Stock Firmware Features

The stock firmware exposes both USB HID flashing/control and a USB serial shell. It loads the selected FPGA bitstream from SPI flash on boot, advertises the configured display timing to the video source, and then drives the connected EPD panel from the selected video input.

Video sources:

- USB-C DisplayPort Alt Mode through the USB-C connector.
- DVI through the Mini-HDMI connector, with USB-C still required for power and USB.
- Auto input selection by default, with manual input selection available through the OSD/menu controls.

Button defaults:

- K1 short press: next mode.
- K1 long press: previous mode.
- K2 short press: open settings.
- K2 long press: power off.
- K3 short press: clear/redraw.
- K3 long press: toggle auto clear.

The OSD/settings menu supports input selection, update-mode selection, lightness and contrast adjustment, auto clear mode/interval/threshold, OSD scale, and button binding changes. The suspend feature follows the host PC sleep state where possible and automatically enters sleep after loss of video signal.

## Display Configuration

The board cannot automatically detect the connected panel. The display resolution and timing must be configured. Release packages include generated configs for the bundled kits, and the firmware also includes a shell command for changing the timing later.

### Built-In Shell

Connect to the USB serial shell and run:

```text
setres <size_in> <x_res> <y_res> <ref_hz> <cvt-rb2|cvt-rb>
```

Examples:

```text
setres 6 1448 1072 75 cvt-rb
setres 13.3 1600 1200 75 cvt-rb2
```

`setres` calculates host timing, TCON timing, screen physical size, saves `config.bin`, and prints the generated values.

### Host Config Generator

Build and run `cfggen`:

```bash
make -C utils/flash_tool/cfggen
utils/flash_tool/cfggen/bin/cfggen 6 1448 1072 75 cvt-rb --out config-6in.bin
utils/flash_tool/cfggen/bin/cfggen 13.3 1600 1200 75 cvt-rb2 --out config-13in.bin
```

Transfer the selected file as `config.bin` using `flash.py` or a diagnostic shell file-transfer path.

Use `cvt-rb` for the 6 inch bundled config. Use `cvt-rb2` for the 13.3 inch bundled config unless a specific panel batch requires otherwise.

## Building

Building from source is currently supported under Linux. Flashing release packages is supported on Linux and macOS, with Windows caveats described above.

Install these build tools:

- host GCC, make, and standard development utilities.
- Python 3 and Python `hidapi`.
- `dfu-util`.
- STM32CubeIDE 2.0.0 for MCU builds.
- `sshpass` for scripted ISE VM access.
- Xilinx ISE 14.7 through the official VM package for FPGA builds.

Clone with submodules:

```bash
git clone --recursive https://gitlab.com/zephray/Glider.git
cd Glider
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

### Xilinx ISE VM Setup

On the Xilinx download site, the VM package is not simply listed as "ISE 14.7 VM". Download the package named "ISE Design Suite for Windows 10 and Windows 11". It is a zip file. After download, ignore the bundled installation wizard and extract `ova/14.7_VM.ova` from the zip.

Import `ova/14.7_VM.ova` into VirtualBox. Other VM software can also work by extracting the virtual disk and creating a VM around it, but keep the VM's NIC MAC address from the OVA. The ISE license inside the VM is tied to that MAC address. Importing the OVA normally preserves the correct NIC MAC address automatically; other VM flows may require setting it manually.

Set the VM NIC to host-only mode if needed so the host can reach it directly. In the examples below, 192.168.56.101 is the VM IP address. Before starting a build, verify connectivity with `ping 192.168.56.101`, then verify SSH with `ssh ise@192.168.56.101`. The default VM SSH user is usually `ise`, and the password is `xilinx`.

### Full Release Build

Do a full release build before using the development flash helpers. This confirms STM32CubeIDE, submodules, the ISE VM, SSH access, `sshpass`, `cfggen`, font generation, and release packaging are all working before any helper attempts to flash hardware.

For a release package:

```bash
scripts/release.sh --ise-host 192.168.56.101 0.1.0
```

The release flow builds the MCU locally, builds all FPGA variants in one ISE VM session, generates fonts, generates display configs, and writes the package to `build/release/<version>/`.

For release-script checks without hardware tools:

```bash
scripts/release.sh --dry-run --ise-host 192.168.56.101 0.1.0
```

## Development Builds

Use the development helpers after a full release build has succeeded. These helpers exist to avoid rebuilding everything during iteration: MCU firmware rebuilds take only a few seconds, and a single FPGA variant rebuild avoids the full four-variant release path.

### MCU Firmware

Rebuild and DFU-flash the MCU firmware:

```bash
scripts/dev_flash_mcu.sh
```

Enter DFU mode first by holding the button closer to the USB port while plugging in USB. The script builds `glider_ec_rtos_dev.bin` under `build/dev/mcu/` and flashes it with `dfu-util`.

### FPGA Bitstream

Build and transfer one FPGA variant:

```bash
scripts/dev_flash_fpga.sh --ise-host 192.168.56.101 --variant 8bit-mono
```

Supported variants are `8bit-mono`, `8bit-k3`, `16bit-mono`, and `16bit-k3`.

The helper uses `scripts/build_caster_ise_vm.sh`, stores output under `build/dev/caster/<variant>/`, and calls `flash.py --skip-mcu --no-fonts --no-config` so FPGA iteration does not ask for MCU or config flashing.

## Manual Flashing

MCU DFU flash:

```bash
dfu-util -a 0 -i 0 -s 0x08000000:leave -D glider_ec_rtos.bin
```

After reboot, connect to the USB serial shell. Useful commands:

```text
ver
setres 6 1448 1072 75 cvt-rb
setcfg get
setcfg save
```

Diagnostic builds also include XMODEM file-transfer commands such as `recv`. Normal release images are intended to use HID transfer through `flash.py`.

## Troubleshooting

- During normal use, the green LED blinks. If something goes wrong, the RED LED turns on.
- If no LED turns on, check the USB-C power cable and the power source.
- There is a screen update LED near the screen connector. If that lights up but no image on the screen, double check the screen is firmly seated.
- If the board powers on but there is no video, check whether the PC has detected the monitor and whether the output is enabled.
- If USB-C DisplayPort Alt Mode is used, make sure the cable supports DisplayPort Alt Mode. Many charge-only USB-C cables will not work for video.
- Use a serial terminal and run `syslog` to see what the firmware is doing. This is often the fastest way to distinguish video-input, config, FPGA-load, and power-state issues.
- If `dfu-util` reports no DFU device, re-enter DFU mode by holding the button closer to the USB port while plugging in USB.
- If `flash.py` cannot find a bitstream, run it from the release `flash_tool` directory or pass `--bitstream`.
- If the display is shifted or unstable, check that the config matches the panel and try the other timing standard with `setres`.
- If the ISE VM build cannot log in, confirm the VM SSH user is `ise`, the password is `xilinx`, the VM is reachable, and `sshpass` is installed.
