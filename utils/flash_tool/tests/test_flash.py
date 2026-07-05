import importlib.util
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


def load_flash_module():
    sys.modules.setdefault("hid", types.SimpleNamespace(device=object))
    flash_path = Path(__file__).resolve().parents[1] / "flash.py"
    spec = importlib.util.spec_from_file_location("glider_flash_tool", flash_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FlashToolTests(unittest.TestCase):
    def setUp(self):
        self.flash = load_flash_module()

    def test_discover_bitstreams_returns_release_variants_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fpga-16bit-k3.bit").write_bytes(b"16k3")
            (root / "fpga-8bit-mono.bit").write_bytes(b"8mono")
            (root / "fpga.bit").write_bytes(b"legacy")

            bitstreams = self.flash.discover_bitstreams(root)

        self.assertEqual(
            [path.name for path in bitstreams],
            ["fpga-8bit-mono.bit", "fpga-16bit-k3.bit"],
        )

    def test_discover_bitstreams_uses_legacy_fpga_bit_when_it_is_the_only_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fpga.bit").write_bytes(b"legacy")

            bitstreams = self.flash.discover_bitstreams(root)

        self.assertEqual([path.name for path in bitstreams], ["fpga.bit"])

    def test_select_bitstream_raises_clear_error_when_no_bitstreams_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, "No FPGA bitstream"):
                self.flash.select_bitstream(Path(tmp))

    def test_select_bitstream_prompts_for_release_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fpga-16bit-k3.bit").write_bytes(b"16k3")
            (root / "fpga-8bit-mono.bit").write_bytes(b"8mono")
            output = io.StringIO()

            selected = self.flash.select_bitstream(
                root,
                input_func=lambda prompt: "2",
                output=output,
            )

        self.assertEqual(selected.name, "fpga-16bit-k3.bit")
        self.assertIn("Select FPGA bitstream", output.getvalue())
        self.assertIn("1) fpga-8bit-mono.bit", output.getvalue())
        self.assertIn("2) fpga-16bit-k3.bit", output.getvalue())

    def test_flash_mcu_returns_false_when_dfu_util_fails(self):
        completed = types.SimpleNamespace(returncode=74)
        with mock.patch.object(self.flash.subprocess, "run", return_value=completed):
            self.assertFalse(self.flash.flash_mcu())

    def test_main_stops_after_failed_dfu_when_user_declines_continue(self):
        with mock.patch.object(self.flash, "flash_mcu", return_value=False), \
                mock.patch.object(self.flash, "ask_yes_no", return_value=False), \
                mock.patch.object(self.flash, "send_files") as send_files:
            result = self.flash.main([])

        self.assertEqual(result, 1)
        send_files.assert_not_called()

    def test_main_continues_after_failed_dfu_when_user_accepts(self):
        with mock.patch.object(self.flash, "flash_mcu", return_value=False), \
                mock.patch.object(self.flash, "ask_yes_no", return_value=True), \
                mock.patch.object(self.flash, "send_files") as send_files:
            result = self.flash.main([])

        self.assertEqual(result, 0)
        send_files.assert_called_once()

    def test_main_can_skip_mcu_and_only_send_selected_bitstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            bitstream = Path(tmp) / "fpga.bit"
            bitstream.write_bytes(b"bit")

            with mock.patch.object(self.flash, "flash_mcu") as flash_mcu, \
                    mock.patch.object(self.flash, "send_files") as send_files:
                result = self.flash.main([
                    "--skip-mcu",
                    "--bitstream", str(bitstream),
                    "--no-fonts",
                ])

        self.assertEqual(result, 0)
        flash_mcu.assert_not_called()
        send_files.assert_called_once_with(
            bitstream_path=bitstream,
            include_fonts=False,
        )


if __name__ == "__main__":
    unittest.main()
