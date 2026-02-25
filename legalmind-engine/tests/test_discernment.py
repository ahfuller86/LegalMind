import unittest
from unittest.mock import MagicMock, patch
import sys

# Since app.modules.discernment imports from app.models, and app.models imports pydantic
# which is missing in the test environment, we must mock these modules BEFORE import.

class TestDiscernment(unittest.TestCase):
    def setUp(self):
        # Prepare mocks for missing dependencies
        self.mock_modules = {
            "docx": MagicMock(),
            "litellm": MagicMock(),
            "pydantic": MagicMock(),
            "app.core.stores": MagicMock(),
            "app.core.config": MagicMock(),
            "app.models": MagicMock(),
        }

        # Apply patch to sys.modules
        self.patcher = patch.dict(sys.modules, self.mock_modules)
        self.patcher.start()

        # Now it is safe to import app.modules.discernment
        # We must reload or import inside the test method if we want fresh mocks,
        # but setUp is fine if we clean up in tearDown.
        # However, to be safe against previous imports, we can force reload or just import here.
        if "app.modules.discernment" in sys.modules:
            del sys.modules["app.modules.discernment"]

        from app.modules.discernment import Discernment
        self.DiscernmentClass = Discernment

    def tearDown(self):
        self.patcher.stop()
        if "app.modules.discernment" in sys.modules:
            del sys.modules["app.modules.discernment"]

    def test_boilerplate_filter(self):
        # Create instance with mocked CaseContext
        mock_case_context = MagicMock()
        discernment = self.DiscernmentClass(mock_case_context)

        # Test exact match (lowercase)
        self.assertTrue(discernment.boilerplate_filter("comes now the plaintiff"), "Should detect 'comes now'")

        # Test mixed case match
        self.assertTrue(discernment.boilerplate_filter("Respectfully Submitted"), "Should be case-insensitive")

        # Test partial match (word inside another word)
        # Note: Current implementation uses 'in', so 'court' in 'courtyard' is True.
        self.assertTrue(discernment.boilerplate_filter("The courtyard was empty"), "Should match 'court' in 'courtyard'")

        # Test no match
        self.assertFalse(discernment.boilerplate_filter("This is a factual statement."), "Should not match non-boilerplate text")

        # Test empty string
        self.assertFalse(discernment.boilerplate_filter(""), "Empty string should not match")

        # Test all keywords defined in the method
        keywords = ["comes now", "respectfully submitted", "wherefore", "judge", "court"]
        for kw in keywords:
            self.assertTrue(discernment.boilerplate_filter(f"Text containing {kw} here"), f"Failed for keyword: {kw}")
            self.assertTrue(discernment.boilerplate_filter(f"Text containing {kw.upper()} here"), f"Failed for keyword: {kw.upper()}")

if __name__ == '__main__':
    unittest.main()
