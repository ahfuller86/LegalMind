import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock modules before importing app.modules.discernment
# This is necessary because app.modules.discernment imports things that might not be available or heavy
# We use patch.dict to safely mock sys.modules for the duration of the test class setup

class TestDiscernment(unittest.TestCase):
    def setUp(self):
        # Create mocks for dependencies
        self.mock_app_core_stores = MagicMock()
        self.mock_app_core_config = MagicMock()
        self.mock_app_models = MagicMock()
        self.mock_docx = MagicMock()
        self.mock_litellm = MagicMock()

        # Define a mock Claim class to behave like the Pydantic model
        class MockClaim:
            def __init__(self, text, expected_modality=None, **kwargs):
                self.text = text
                self.expected_modality = expected_modality
                # Allow other attributes but we focus on text and expected_modality
                for k, v in kwargs.items():
                    setattr(self, k, v)

        # Assign the mock Claim to the mock app.models module
        self.mock_app_models.Claim = MockClaim
        self.mock_app_models.ClaimType = MagicMock()
        self.mock_app_models.RoutingDecision = MagicMock()

        # Assign CaseContext to app.core.stores
        self.mock_app_core_stores.CaseContext = MagicMock()

        # Assign load_config to app.core.config
        self.mock_app_core_config.load_config = MagicMock()

        # Prepare the sys.modules patcher
        self.modules_patcher = patch.dict(sys.modules, {
            "app.core.stores": self.mock_app_core_stores,
            "app.core.config": self.mock_app_core_config,
            "app.models": self.mock_app_models,
            "docx": self.mock_docx,
            "litellm": self.mock_litellm,
            # We also need to mock pydantic if it's used directly in the module or by other imports we rely on
            # The code under test uses standard library mostly, but app.models uses pydantic
            # Since we mocked app.models, we should be fine, but let's be safe
        })
        self.modules_patcher.start()

        # Now import the module under test
        # We need to make sure it's reloaded if it was already imported, but here it's fresh
        if "app.modules.discernment" in sys.modules:
            del sys.modules["app.modules.discernment"]

        from app.modules.discernment import Discernment
        self.Discernment = Discernment

        # Initialize Discernment with a mock CaseContext
        self.mock_case_context_instance = self.mock_app_core_stores.CaseContext()
        self.discernment = self.Discernment(self.mock_case_context_instance)

    def tearDown(self):
        self.modules_patcher.stop()

    def test_modality_tagger_testimony(self):
        """Test that testimony keywords trigger 'testimony' modality."""
        # Test "witness"
        claim1 = self.mock_app_models.Claim(text="The witness saw the event.")
        self.discernment.modality_tagger(claim1)
        self.assertEqual(claim1.expected_modality, "testimony")

        # Test "said"
        claim2 = self.mock_app_models.Claim(text="He said that it happened.")
        self.discernment.modality_tagger(claim2)
        self.assertEqual(claim2.expected_modality, "testimony")

        # Test "testified"
        claim3 = self.mock_app_models.Claim(text="She testified in court.")
        self.discernment.modality_tagger(claim3)
        self.assertEqual(claim3.expected_modality, "testimony")

    def test_modality_tagger_video(self):
        """Test that video keywords trigger 'video' modality."""
        # Test "video"
        claim1 = self.mock_app_models.Claim(text="The video shows the incident.")
        self.discernment.modality_tagger(claim1)
        self.assertEqual(claim1.expected_modality, "video")

        # Test "footage"
        claim2 = self.mock_app_models.Claim(text="Review the footage carefully.")
        self.discernment.modality_tagger(claim2)
        self.assertEqual(claim2.expected_modality, "video")

        # Test "camera"
        claim3 = self.mock_app_models.Claim(text="The camera was recording.")
        self.discernment.modality_tagger(claim3)
        self.assertEqual(claim3.expected_modality, "video")

    def test_modality_tagger_image(self):
        """Test that image keywords trigger 'image' modality."""
        # Test "photo"
        claim1 = self.mock_app_models.Claim(text="Look at this photo.")
        self.discernment.modality_tagger(claim1)
        self.assertEqual(claim1.expected_modality, "image")

        # Test "image"
        claim2 = self.mock_app_models.Claim(text="The image is blurry.")
        self.discernment.modality_tagger(claim2)
        self.assertEqual(claim2.expected_modality, "image")

        # Test "picture"
        claim3 = self.mock_app_models.Claim(text="A picture of the scene.")
        self.discernment.modality_tagger(claim3)
        self.assertEqual(claim3.expected_modality, "image")

    def test_modality_tagger_precedence(self):
        """Test the precedence of modality tagging (Testimony > Video > Image)."""
        # Testimony (witness) + Video -> Testimony wins
        claim1 = self.mock_app_models.Claim(text="The witness watched the video.")
        self.discernment.modality_tagger(claim1)
        self.assertEqual(claim1.expected_modality, "testimony")

        # Video + Image -> Video wins
        claim2 = self.mock_app_models.Claim(text="A video of the photo.")
        self.discernment.modality_tagger(claim2)
        self.assertEqual(claim2.expected_modality, "video")

    def test_modality_tagger_no_match(self):
        """Test that no modality is set if no keywords match."""
        claim = self.mock_app_models.Claim(text="The document was signed on Tuesday.")
        self.discernment.modality_tagger(claim)
        self.assertIsNone(claim.expected_modality)

    def test_modality_tagger_case_insensitivity(self):
        """Test that tagging is case-insensitive."""
        claim = self.mock_app_models.Claim(text="THE WITNESS WAS THERE.")
        self.discernment.modality_tagger(claim)
        self.assertEqual(claim.expected_modality, "testimony")

if __name__ == '__main__':
    unittest.main()
