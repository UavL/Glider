#!/usr/bin/env python3
import importlib.util
import pathlib
import struct
import sys
import unittest


sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
FONT_BIN_PATH = ROOT / "font_bin.py"


def load_font_bin():
    spec = importlib.util.spec_from_file_location("font_bin", FONT_BIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiny_font_blob():
    header = struct.pack(
        "<9I",
        0x46534F47,
        1,
        1,
        1,
        2,
        65,
        2,
        3,
        6,
    )
    glyphs = struct.pack(
        "<6I",
        3, 0xA0000000, 0x40000000,
        5, 0xF8000000, 0x88000000,
    )
    return header + glyphs


class FontBinTest(unittest.TestCase):
    def test_checked_in_release_fonts_parse(self):
        font_bin = load_font_bin()
        font_dir = ROOT.parents[1] / "utils" / "flash_tool" / "fonts"

        for size in (16, 20, 28):
            with self.subTest(size=size):
                path = font_dir / f"font_quicksand_{size}.bin"
                self.assertTrue(path.exists(), f"missing checked-in font {path}")
                font = font_bin.FontBin.from_file(path)
                self.assertEqual(32, font.offset)
                self.assertEqual(95, font.chars)
                self.assertGreater(font.height, 0)

    def test_round_trip_preserves_valid_font(self):
        font_bin = load_font_bin()
        font = font_bin.FontBin.from_bytes(tiny_font_blob())

        self.assertEqual(2, font.height)
        self.assertEqual(65, font.offset)
        self.assertEqual(["A", "B"], font.characters())
        self.assertEqual(tiny_font_blob(), font.to_bytes())

    def test_pixel_edit_updates_row_word(self):
        font_bin = load_font_bin()
        font = font_bin.FontBin.from_bytes(tiny_font_blob())

        self.assertTrue(font.get_pixel("A", 0, 0))
        self.assertFalse(font.get_pixel("A", 1, 0))
        font.set_pixel("A", 1, 0, True)
        font.set_pixel("A", 0, 0, False)

        self.assertFalse(font.get_pixel("A", 0, 0))
        self.assertTrue(font.get_pixel("A", 1, 0))
        self.assertEqual(0x60000000, font.glyph("A").rows[0])

    def test_width_edit_is_validated(self):
        font_bin = load_font_bin()
        font = font_bin.FontBin.from_bytes(tiny_font_blob())

        font.set_width("B", 7)
        self.assertEqual(7, font.glyph("B").width)
        with self.assertRaises(ValueError):
            font.set_width("B", 33)

    def test_rejects_truncated_payload(self):
        font_bin = load_font_bin()

        with self.assertRaises(font_bin.FontFormatError):
            font_bin.FontBin.from_bytes(tiny_font_blob()[:-4])

    def test_rejects_unsupported_header(self):
        font_bin = load_font_bin()
        blob = bytearray(tiny_font_blob())
        struct.pack_into("<I", blob, 4, 2)

        with self.assertRaises(font_bin.FontFormatError):
            font_bin.FontBin.from_bytes(blob)


if __name__ == "__main__":
    unittest.main()
