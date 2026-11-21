"""Optional real-host import check, explicitly skipped when HA is absent."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True


@unittest.skipUnless(importlib.util.find_spec("homeassistant"), "Home Assistant is not installed: host integration test pending")
class HomeAssistantImportTests(unittest.TestCase):
    def test_adapter_imports_in_installed_homeassistant(self):
        root = str(Path(__file__).resolve().parents[1])
        sys.path.insert(0, root)
        try:
            for module in ["config_flow", "runtime", "sensor", "button"]:
                importlib.import_module("custom_components.watermeter_ai." + module)
        finally:
            sys.path.remove(root)


if __name__ == "__main__":
    unittest.main()
