import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock pydantic since it might be missing in the test environment
mock_pydantic = MagicMock()
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = lambda default=None, **kwargs: default
sys.modules["pydantic"] = mock_pydantic

# Mock heavy dependencies to avoid import errors or side effects during testing
sys.modules["app.modules.intake"] = MagicMock()
sys.modules["app.modules.conversion"] = MagicMock()
sys.modules["app.modules.structuring"] = MagicMock()
sys.modules["app.modules.preservation"] = MagicMock()
sys.modules["app.modules.discernment"] = MagicMock()
sys.modules["app.modules.inquiry"] = MagicMock()
sys.modules["app.modules.adjudication"] = MagicMock()
sys.modules["app.modules.chronicle"] = MagicMock()
sys.modules["app.modules.validation"] = MagicMock()
sys.modules["app.modules.sentinel"] = MagicMock()
# Also mock stores if needed, but we might want CaseContext from it
# app.core.stores is imported in dominion.py

from app.core.config import load_config
# We need to import Dominion after mocking modules
from app.modules.dominion import Dominion

class TestConfigStorage(unittest.TestCase):
    def test_load_config_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            self.assertEqual(config.STORAGE_PATH, "./storage")

    def test_load_config_custom(self):
        with patch.dict(os.environ, {"LEGALMIND_STORAGE_PATH": "/custom/storage"}):
            config = load_config()
            self.assertEqual(config.STORAGE_PATH, "/custom/storage")

    @patch("app.modules.dominion.CaseContext")
    @patch("app.modules.dominion.load_config")
    def test_dominion_uses_configured_path(self, mock_load_config, mock_case_context):
        # Setup config mock
        mock_config = MagicMock()
        mock_config.STORAGE_PATH = "/configured/path"
        mock_load_config.return_value = mock_config

        # Mock initial CaseContext
        initial_context = MagicMock()
        initial_context.base_path = "/default/storage/case123"

        # Initialize Dominion
        dominion = Dominion(initial_context)

        # Run async method
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(dominion.case_workspace_init("new_case_name"))
        finally:
            loop.close()

        # Check that CaseContext was instantiated with the path from config
        # calls[0] is init, so checking constructor call
        # Mock class call is checkable
        mock_case_context.assert_called_with("new_case_name", base_storage_path="/configured/path")

if __name__ == "__main__":
    unittest.main()
