import os
import sys
import unittest
from unittest.mock import patch, MagicMock

class TestConfigStorage(unittest.TestCase):
    def setUp(self):
        # Prepare mocks for dependencies
        self.mock_pydantic = MagicMock()

        # Mock BaseModel behavior
        class MockBaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        self.mock_pydantic.BaseModel = MockBaseModel

        # Mock Field behavior
        def mock_field(default=None, **kwargs):
            return default
        self.mock_pydantic.Field = mock_field

        # Create a dict of modules to patch
        self.modules_to_patch = {
            "pydantic": self.mock_pydantic,
            "app.core.stores": MagicMock(),
        }

        # Add app modules
        for mod in ["intake", "conversion", "structuring", "preservation", "discernment", "inquiry", "adjudication", "chronicle", "validation", "sentinel"]:
            self.modules_to_patch[f"app.modules.{mod}"] = MagicMock()

        # Start patching sys.modules
        self.module_patcher = patch.dict(sys.modules, self.modules_to_patch)
        self.module_patcher.start()

        # Ensure target modules are re-imported to pick up mocks
        self._clean_modules()

    def tearDown(self):
        self._clean_modules()
        self.module_patcher.stop()

    def _clean_modules(self):
        # Remove the modules under test from sys.modules so they are re-imported
        for mod in ["app.core.config", "app.modules.dominion"]:
            if mod in sys.modules:
                del sys.modules[mod]

    def test_load_config_default(self):
        from app.core.config import load_config
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            self.assertEqual(config.STORAGE_PATH, "./storage")

    def test_load_config_custom(self):
        from app.core.config import load_config
        with patch.dict(os.environ, {"LEGALMIND_STORAGE_PATH": "/custom/storage"}):
            config = load_config()
            self.assertEqual(config.STORAGE_PATH, "/custom/storage")

    def test_dominion_uses_configured_path(self):
        # We need to import Dominion inside the test method (or after setUp)
        from app.modules.dominion import Dominion

        # We need to patch load_config and CaseContext in dominion module
        # Since we just imported it, we can patch it there.

        with patch("app.modules.dominion.load_config") as mock_load_config, \
             patch("app.modules.dominion.CaseContext") as mock_case_context:

            mock_config = MagicMock()
            mock_config.STORAGE_PATH = "/configured/path"
            mock_load_config.return_value = mock_config

            initial_context = MagicMock()
            initial_context.base_path = "/initial/path"

            dominion = Dominion(initial_context)

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(dominion.case_workspace_init("new_case"))
            finally:
                loop.close()

            mock_case_context.assert_called_with("new_case", base_storage_path="/configured/path")

if __name__ == "__main__":
    unittest.main()
