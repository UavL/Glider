import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


def load_factory_module():
    sys.modules.setdefault("hid", types.SimpleNamespace(device=object))
    sys.modules.setdefault("serial", types.SimpleNamespace(Serial=object))
    tool_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("glider_factory_tool", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FactoryToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_factory_module()

    def test_config_command_for_6_inch_uses_cvt_rb(self):
        command = self.tool.cfggen_command_for_screen(6, "config.bin")

        self.assertEqual(
            command,
            ["./cfggen/bin/cfggen", "6", "1448", "1072", "75",
             "cvt-rb", "--out", "config.bin"],
        )

    def test_config_command_for_13_inch_uses_cvt_rb2(self):
        command = self.tool.cfggen_command_for_screen(13, "config.bin")

        self.assertEqual(
            command,
            ["./cfggen/bin/cfggen", "13.3", "1600", "1200", "75",
             "cvt-rb2", "--out", "config.bin"],
        )

    def test_config_flashing_is_default_on_and_conditional(self):
        init_source = inspect.getsource(self.tool.App.__init__)
        task_source = inspect.getsource(self.tool.App.flash_test_task)

        self.assertIn("self.flash_config = tk.BooleanVar(value=True)", init_source)
        self.assertIn("tk.Checkbutton", init_source)
        self.assertIn("if self.flash_config.get():", task_source)


if __name__ == "__main__":
    unittest.main()
