import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.modules.intake import Intake
from app.core.config import load_config

class TestIntakeSecurity(unittest.TestCase):
    def setUp(self):
        # Mock CaseContext since it's required for Intake init but not used in _validate_path
        self.mock_case_context = MagicMock()
        self.intake = Intake(self.mock_case_context)

    def test_default_config_excludes_dot(self):
        """Test that default configuration does not include '.' in allowed paths."""
        # Unset env var to ensure we test defaults
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            self.assertNotIn(".", config.ALLOWED_INPUT_PATHS)
            self.assertIn("/tmp", config.ALLOWED_INPUT_PATHS)

    def test_validate_path_denies_cwd(self):
        """Test that _validate_path denies access to files in CWD if not explicitly allowed."""
        # Create a dummy file in CWD
        test_file = "test_sensitive_file.txt"
        with open(test_file, "w") as f:
            f.write("secret")

        try:
            # By default, CWD should be denied
            is_allowed = self.intake._validate_path(test_file)
            self.assertFalse(is_allowed, "Access to file in CWD should be denied by default")

            # Also check absolute path
            abs_path = os.path.abspath(test_file)
            is_allowed = self.intake._validate_path(abs_path)
            self.assertFalse(is_allowed, f"Access to absolute path {abs_path} should be denied")

        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_validate_path_allows_tmp(self):
        """Test that /tmp is allowed."""
        test_file = "/tmp/legalmind_test_file.txt"
        with open(test_file, "w") as f:
            f.write("safe")

        try:
            is_allowed = self.intake._validate_path(test_file)
            self.assertTrue(is_allowed, "Access to /tmp should be allowed")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_explicit_dot_ignored_in_intake(self):
        """Test that even if '.' is in config, intake ignores it (if that's the implemented behavior)."""
        # We implemented a fix in intake.py that explicitly continues if p == "."
        # So even if we force it into config, it should be ignored by the logic in _validate_path

        # We need to patch load_config to return a config with "."
        # Since load_config returns a Pydantic model, we mock it or construct it

        # Let's verify the behavior of Intake._validate_path with a mocked config
        with patch("app.modules.intake.load_config") as mock_load_config:
            mock_config = MagicMock()
            mock_config.ALLOWED_INPUT_PATHS = [".", "/tmp"]
            mock_load_config.return_value = mock_config

            test_file = "test_should_be_denied.txt"
            with open(test_file, "w") as f:
                f.write("data")

            try:
                is_allowed = self.intake._validate_path(test_file)
                self.assertFalse(is_allowed, "Intake should ignore '.' in config")
            finally:
                if os.path.exists(test_file):
                    os.remove(test_file)

if __name__ == "__main__":
    unittest.main()
