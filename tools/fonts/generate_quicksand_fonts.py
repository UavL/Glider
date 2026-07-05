#!/usr/bin/env python3
import argparse
import math
import pathlib
import struct
import sys

from PIL import Image, ImageDraw, ImageFont


OSD_FONT_MAGIC = 0x46534F47
OSD_FONT_VERSION = 1
OSD_FONT_TYPE_PROPORTIONAL_ASCII = 1
OSD_FONT_PIXFMT_Y1 = 1
SIZES = (16, 20, 28)
THRESHOLDS = {
    16: 129,
    20: 150,
    28: 160
}
DEFAULT_THRESHOLD = 128
ASCII_FIRST = 32
ASCII_LAST = 126
DEFAULT_TTF_CANDIDATES = (
    pathlib.Path("usr/share/fonts/truetype/quicksand/Quicksand-Regular.ttf"),
    pathlib.Path("usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf"),
    pathlib.Path("usr/share/fonts/truetype/quicksand/Quicksand-VariableFont_wght.ttf"),
)


def find_quicksand_ttf(root=pathlib.Path("/")):
    for candidate in DEFAULT_TTF_CANDIDATES:
        path = root / candidate
        if path.exists():
            return path
    return None


def resolve_ttf(explicit_ttf=None, root=pathlib.Path("/")):
    if explicit_ttf is not None:
        return pathlib.Path(explicit_ttf)
    return find_quicksand_ttf(root)


def _glyph_bounds(font, chars):
    top = 0
    bottom = 0
    max_width = 1
    for ch in chars:
        bbox = font.getbbox(ch)
        advance = int(math.ceil(font.getlength(ch)))
        left = min(0, bbox[0])
        width = max(advance, bbox[2] - left)
        max_width = max(max_width, width)
        top = min(top, bbox[1])
        bottom = max(bottom, bbox[3])
    return top, bottom, max_width


def _render_glyph_words(font, ch, max_width, height, top, threshold):
    bbox = font.getbbox(ch)
    advance = int(math.ceil(font.getlength(ch)))
    left = min(0, bbox[0])
    width = max(advance, bbox[2] - left, 1)
    row_words = (max_width + 31) // 32
    image = Image.new("L", (max_width, height), 0)
    draw = ImageDraw.Draw(image)
    draw.text((-left, -top), ch, font=font, fill=255)

    words = [width]
    for y in range(height):
        row = [0] * row_words
        for x in range(width):
            if image.getpixel((x, y)) >= threshold:
                row[x // 32] |= 0x80000000 >> (x % 32)
        words.extend(row)
    return words


def build_font_words(ttf, size):
    chars = [chr(ch) for ch in range(ASCII_FIRST, ASCII_LAST + 1)]
    font = ImageFont.truetype(str(ttf), size)
    top, bottom, max_width = _glyph_bounds(font, chars)
    height = max(1, bottom - top)
    row_words = (max_width + 31) // 32
    glyph_words = 1 + height * row_words
    data = []
    for ch in chars:
        glyph = _render_glyph_words(font, ch, max_width, height, top,
                THRESHOLDS.get(size, DEFAULT_THRESHOLD))
        if len(glyph) != glyph_words:
            raise ValueError(f"internal glyph size mismatch for {ch!r}")
        data.extend(glyph)
    return height, glyph_words, data


def generate_font_bin(ttf, size, output_path):
    height, glyph_words, data = build_font_words(ttf, size)
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(
        "<9I",
        OSD_FONT_MAGIC,
        OSD_FONT_VERSION,
        OSD_FONT_TYPE_PROPORTIONAL_ASCII,
        OSD_FONT_PIXFMT_Y1,
        height,
        ASCII_FIRST,
        ASCII_LAST - ASCII_FIRST + 1,
        glyph_words,
        len(data),
    )
    payload = struct.pack("<" + "I" * len(data), *data)
    output_path.write_bytes(header + payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate Glider Quicksand OSD font binaries.")
    parser.add_argument("--ttf", type=pathlib.Path,
            help="path to Quicksand TTF; defaults to Ubuntu's packaged Quicksand font if present")
    parser.add_argument("--out-dir", type=pathlib.Path,
            default=pathlib.Path(__file__).resolve().parents[2] / "utils" / "flash_tool" / "fonts",
            help="directory for generated .bin fonts")
    args = parser.parse_args(argv)

    ttf = resolve_ttf(args.ttf)
    if ttf is None:
        print("error: missing Quicksand TTF; pass --ttf or install Ubuntu's fonts-quicksand package", file=sys.stderr)
        return 1
    if not ttf.exists():
        print(f"error: missing TTF file: {ttf}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        bin_output = args.out_dir / f"font_quicksand_{size}.bin"
        try:
            generate_font_bin(ttf, size, bin_output)
        except Exception as exc:
            print(f"error: failed to generate size {size}: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
