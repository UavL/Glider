#!/usr/bin/env python3
import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "generate_quicksand_fonts.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_quicksand_fonts", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_test_ttf():
    candidates = [
        pathlib.Path("/usr/share/fonts/truetype/quicksand/Quicksand-Bold.ttf"),
        pathlib.Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise unittest.SkipTest("no TrueType test font available")


class QuicksandGeneratorTest(unittest.TestCase):
    def test_prefers_ubuntu_packaged_quicksand_bold(self):
        generator = load_generator()

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            ubuntu_dir = root / "usr" / "share" / "fonts" / "truetype" / "quicksand"
            ubuntu_dir.mkdir(parents=True)
            expected = ubuntu_dir / "Quicksand-Bold.ttf"
            expected.write_bytes(b"fake")

            self.assertEqual(expected, generator.find_quicksand_ttf(root))

    def test_explicit_ttf_overrides_default_search(self):
        generator = load_generator()

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            ubuntu_dir = root / "usr" / "share" / "fonts" / "truetype" / "quicksand"
            ubuntu_dir.mkdir(parents=True)
            (ubuntu_dir / "Quicksand-Bold.ttf").write_bytes(b"fake")
            explicit = root / "custom.ttf"
            explicit.write_bytes(b"fake")

            self.assertEqual(explicit, generator.resolve_ttf(explicit, root))

    def test_direct_generator_preserves_proportional_widths(self):
        generator = load_generator()
        ttf = find_test_ttf()

        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "font.bin"
            generator.generate_font_bin(ttf, 18, out)
            data = out.read_bytes()

        header = struct.unpack_from("<9I", data, 0)
        self.assertEqual(generator.OSD_FONT_MAGIC, header[0])
        self.assertEqual(generator.OSD_FONT_VERSION, header[1])
        self.assertEqual(generator.OSD_FONT_TYPE_PROPORTIONAL_ASCII, header[2])
        self.assertEqual(generator.OSD_FONT_PIXFMT_Y1, header[3])
        self.assertEqual(32, header[5])
        self.assertEqual(95, header[6])

        glyph_words = header[7]
        words = struct.unpack_from("<" + "I" * header[8], data, 9 * 4)
        width_i = words[(ord("i") - 32) * glyph_words]
        width_w = words[(ord("W") - 32) * glyph_words]
        self.assertGreater(width_i, 0)
        self.assertGreater(width_w, width_i)

    def test_cli_generates_expected_font_files(self):
        generator = load_generator()
        ttf = find_test_ttf()

        with tempfile.TemporaryDirectory() as td:
            out_dir = pathlib.Path(td)
            rc = generator.main(["--ttf", str(ttf), "--out-dir", str(out_dir)])
            self.assertEqual(0, rc)
            for size in generator.SIZES:
                self.assertTrue((out_dir / f"font_quicksand_{size}.bin").exists())


if __name__ == "__main__":
    unittest.main()
