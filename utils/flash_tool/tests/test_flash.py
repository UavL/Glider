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

    class _FakeDfuStdout:
        def __init__(self, lines, captured_output):
            self.lines = lines
            self.captured_output = captured_output
            self.index = 0
            self.saw_live_output = False

        def readline(self):
            if self.index == 1:
                self.saw_live_output = "Erase" in self.captured_output.getvalue()
            if self.index >= len(self.lines):
                return ""
            line = self.lines[self.index]
            self.index += 1
            return line

    class _FakeDfuProcess:
        def __init__(self, lines, returncode, captured_output):
            self.stdout = FlashToolTests._FakeDfuStdout(lines, captured_output)
            self.returncode = returncode

        def poll(self):
            if self.stdout.index >= len(self.stdout.lines):
                return self.returncode
            return None

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

    def test_discover_configs_returns_release_configs_in_panel_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configs = root / "configs"
            configs.mkdir()
            (configs / "config-13in.bin").write_bytes(b"13")
            (configs / "config-6in.bin").write_bytes(b"6")

            found = self.flash.discover_configs(root)

        self.assertEqual(
            [path.name for path in found],
            ["config-6in.bin", "config-13in.bin"],
        )

    def test_select_config_prompts_for_release_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configs = root / "configs"
            configs.mkdir()
            (configs / "config-6in.bin").write_bytes(b"6")
            (configs / "config-13in.bin").write_bytes(b"13")
            output = io.StringIO()

            selected = self.flash.select_config(
                root,
                input_func=lambda prompt: "2",
                output=output,
            )

        self.assertEqual(selected.name, "config-13in.bin")
        self.assertIn("Select display config", output.getvalue())
        self.assertIn("1) config-6in.bin", output.getvalue())
        self.assertIn("2) config-13in.bin", output.getvalue())

    def test_flash_mcu_returns_false_when_dfu_util_fails(self):
        captured_output = io.StringIO()
        process = self._FakeDfuProcess([
            "No DFU capable USB device available\n",
        ], returncode=74, captured_output=captured_output)

        with mock.patch.object(self.flash.subprocess, "Popen", return_value=process), \
                mock.patch.object(self.flash.sys, "stdout", new=captured_output):
            self.assertFalse(self.flash.flash_mcu())

    def test_flash_mcu_accepts_leave_status_error_after_successful_download(self):
        captured_output = io.StringIO()
        process = self._FakeDfuProcess([
            'DfuSe interface name: "Internal Flash   "',
            "Download done.\n",
            "File downloaded successfully\n",
            "Submitting leave request...\n",
            "dfu-util: Error during download get_status\n",
        ], returncode=74, captured_output=captured_output)

        with mock.patch.object(self.flash.subprocess, "Popen", return_value=process), \
                mock.patch.object(self.flash.sys, "stdout", new=captured_output):
            self.assertTrue(self.flash.flash_mcu())

    def test_flash_mcu_streams_dfu_util_output_while_process_is_running(self):
        captured_output = io.StringIO()
        process = self._FakeDfuProcess([
            "Erase   [=========] 50%\n",
            "Download done.\n",
            "File downloaded successfully\n",
            "dfu-util: Error during download get_status\n",
        ], returncode=74, captured_output=captured_output)

        with mock.patch.object(self.flash.subprocess, "Popen", return_value=process), \
                mock.patch.object(self.flash.sys, "stdout", new=captured_output):
            self.assertTrue(self.flash.flash_mcu())

        self.assertTrue(process.stdout.saw_live_output)

    def test_main_stops_after_failed_dfu_when_user_declines_continue(self):
        with mock.patch.object(self.flash, "flash_mcu", return_value=False), \
                mock.patch.object(self.flash, "ask_yes_no", return_value=False), \
                mock.patch.object(self.flash, "send_files") as send_files, \
                mock.patch.object(self.flash.sys, "stdout", new=io.StringIO()):
            result = self.flash.main([])

        self.assertEqual(result, 1)
        send_files.assert_not_called()

    def test_main_continues_after_failed_dfu_when_user_accepts(self):
        with mock.patch.object(self.flash, "flash_mcu", return_value=False), \
                mock.patch.object(self.flash, "ask_yes_no", return_value=True), \
                mock.patch.object(self.flash, "send_files") as send_files, \
                mock.patch.object(self.flash.sys, "stdout", new=io.StringIO()):
            result = self.flash.main([])

        self.assertEqual(result, 0)
        send_files.assert_called_once_with(
            bitstream_path=None,
            include_fonts=True,
            config_path=None,
            include_config=True,
        )

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
                    "--no-config",
                ])

        self.assertEqual(result, 0)
        flash_mcu.assert_not_called()
        send_files.assert_called_once_with(
            bitstream_path=bitstream,
            include_fonts=False,
            config_path=None,
            include_config=False,
        )

    def test_main_prompts_for_config_by_default(self):
        with mock.patch.object(self.flash, "flash_mcu", return_value=True), \
                mock.patch.object(self.flash, "ask_yes_no", return_value=True) as ask_yes_no, \
                mock.patch.object(self.flash, "send_files") as send_files:
            result = self.flash.main([])

        self.assertEqual(result, 0)
        ask_yes_no.assert_called_once_with(
            "Flash display config file?",
            default=True,
        )
        send_files.assert_called_once_with(
            bitstream_path=None,
            include_fonts=True,
            config_path=None,
            include_config=True,
        )

    def test_send_files_transfers_selected_config_as_config_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bitstream = root / "fpga.bit"
            bitstream.write_bytes(b"bit")
            fonts = root / "fonts"
            fonts.mkdir()
            for font in self.flash.FONT_FILES:
                (fonts / font).write_bytes(b"font")
            config = root / "configs" / "config-6in.bin"
            config.parent.mkdir()
            config.write_bytes(b"cfg")

            sent = []
            fake_hid = object()
            with mock.patch.object(self.flash, "open_dev", return_value=fake_hid), \
                    mock.patch.object(self.flash, "send_file", side_effect=lambda h, src, dst: sent.append((Path(src).name, dst))):
                self.flash.send_files(
                    bitstream_path=bitstream,
                    include_fonts=False,
                    config_path=config,
                    include_config=True,
                )

        self.assertIn(("config-6in.bin", "config.bin"), sent)


if __name__ == "__main__":
    unittest.main()
