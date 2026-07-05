# Glider OSD Font Tools

The Gen1 settings OSD uses proportional ASCII fonts loaded from SPIFFS. The font binaries under `Glider/utils/flash_tool/fonts/` are checked into the repo so they can be manually tuned and shipped as-is.

Release packaging copies those checked-in `.bin` files. It does not regenerate fonts from TrueType files.

## Edit the Checked-In Fonts

Open a font binary in the bitmap editor:

```bash
python3 Glider/tools/fonts/edit_font.py Glider/utils/flash_tool/fonts/font_quicksand_20.bin
```

Select a glyph from the list, click pixels in the grid to toggle them, adjust the glyph width if needed, then save. The editor writes the same binary format consumed by the firmware and flash tool.

The checked-in font files are:

- `Glider/utils/flash_tool/fonts/font_quicksand_16.bin`
- `Glider/utils/flash_tool/fonts/font_quicksand_20.bin`
- `Glider/utils/flash_tool/fonts/font_quicksand_28.bin`

## Regenerate From TTF

Required local inputs:

- Quicksand TTF. On Ubuntu, the `fonts-quicksand` package provides
  `/usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf`, and the generator
  uses it by default.
- Python Pillow, which provides the FreeType-backed TTF rasterizer

Generate the SPIFFS font binaries:

```bash
python3 Glider/tools/fonts/generate_quicksand_fonts.py
```

Use `--ttf /path/to/Quicksand.ttf` to override the system font.

The generator writes the checked-in font paths listed above. Treat this as a starting-over operation: it replaces manual pixel edits in those files.
