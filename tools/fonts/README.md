# Glider OSD Font Generation

The Gen1 settings OSD uses Quicksand proportional ASCII fonts loaded from SPIFFS.
Use `generate_quicksand_fonts.py` to generate the font binaries directly from a
TrueType font through Pillow/FreeType.

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

The script writes:

- `Glider/utils/flash_tool/fonts/font_quicksand_16.bin`
- `Glider/utils/flash_tool/fonts/font_quicksand_20.bin`
- `Glider/utils/flash_tool/fonts/font_quicksand_28.bin`

Release builds intentionally do not download fonts. If these binaries are missing,
generate them first from a local TTF so the release output is reproducible.
