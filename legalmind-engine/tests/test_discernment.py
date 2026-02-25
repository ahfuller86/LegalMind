import unittest
from unittest.mock import patch, MagicMock, Mock
import os
import sys

# Add the project root to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Mocking Infrastructure ---

def mock_module(module_name, **kwargs):
    """Mocks a module in sys.modules to allow importing code that depends on it."""
    if module_name not in sys.modules:
        mock = MagicMock()
        for key, value in kwargs.items():
            setattr(mock, key, value)
        sys.modules[module_name] = mock
        return mock
    return sys.modules[module_name]

# Mock heavy/missing dependencies
# We need to do this BEFORE importing app.modules.discernment
# 1. docx
mock_module('docx')
# 2. litellm
mock_module('litellm')
# 3. pydantic (if missing)
try:
    import pydantic
except ImportError:
    # Minimal mock for pydantic.BaseModel and Field
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump_json(self):
            return "{}"
        @classmethod
        def model_validate(cls, obj):
            return cls(**obj)

    mock_pydantic = mock_module('pydantic')
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.Field = MagicMock()

# Now we can safely import our app modules
# However, app.models imports pydantic. If we mocked it, it should work.
# But app.core.stores imports app.models.

try:
    from app.modules.discernment import Discernment
    from app.models import Claim, ClaimType, RoutingDecision
    from app.core.stores import CaseContext
except ImportError as e:
    # We rely on imports working after mocking sys.modules.
    # If this fails, we can't test properly, so re-raise.
    raise e

class TestDiscernment(unittest.TestCase):
    def setUp(self):
        # Mock CaseContext to avoid file system operations
        self.mock_case_context = MagicMock(spec=CaseContext)
        self.discernment = Discernment(self.mock_case_context)

    def test_boilerplate_filter(self):
        # Test boilerplate strings
        self.assertTrue(self.discernment.boilerplate_filter("Comes now the plaintiff"))
        self.assertTrue(self.discernment.boilerplate_filter("Respectfully submitted by counsel"))
        self.assertTrue(self.discernment.boilerplate_filter("WHEREFORE, checking case sensitivity"))

        # Test non-boilerplate strings
        self.assertFalse(self.discernment.boilerplate_filter("The witness stated he saw the car."))
        self.assertFalse(self.discernment.boilerplate_filter("This is a factual claim about the incident."))

    def test_modality_tagger(self):
        # Create a dummy claim
        claim = Claim(
            claim_id="123",
            text="The witness testified that he saw the light.",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            routing=RoutingDecision.VERIFY
        )

        # Test "testimony" tagging
        self.discernment.modality_tagger(claim)
        self.assertEqual(claim.expected_modality, "testimony")

        # Test "video" tagging
        claim.text = "The video footage clearly shows the accident."
        claim.expected_modality = None # Reset
        self.discernment.modality_tagger(claim)
        self.assertEqual(claim.expected_modality, "video")

        # Test "image" tagging
        claim.text = "This photo depicts the damage."
        claim.expected_modality = None # Reset
        self.discernment.modality_tagger(claim)
        self.assertEqual(claim.expected_modality, "image")

        # Test no tag
        claim.text = "The car was red."
        claim.expected_modality = None # Reset
        self.discernment.modality_tagger(claim)
        self.assertIsNone(claim.expected_modality)

    def test_heuristic_extract(self):
        text = "This is a short sentence. This is a longer sentence that should be extracted as a claim because it has enough characters and is not boilerplate. Boilerplate comes now."

        claims = self.discernment._heuristic_extract(text)

        self.assertEqual(len(claims), 2)
        # Checking first claim
        # Since _heuristic_extract processes sentences in order
        # 1. "This is a short sentence" (len 24 > 20) -> Claim
        # 2. "This is a longer sentence..." -> Claim
        # 3. "Boilerplate comes now" -> Filtered

        # NOTE: logic splits by ".", so "This is a short sentence" is first.
        self.assertEqual(claims[0].text, "This is a short sentence")
        self.assertIn("This is a longer sentence", claims[1].text)
        self.assertEqual(claims[0].type, ClaimType.FACTUAL)
        self.assertEqual(claims[0].source_location, "heuristic_body")

    @patch('app.modules.discernment.docx.Document')
    @patch('app.modules.discernment.load_config')
    @patch('app.modules.discernment.os.getenv')
    def test_extract_claims_heuristic_fallback(self, mock_getenv, mock_load_config, mock_docx):
        # Setup mocks
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "This is a claim that should be extracted heuristically."
        mock_doc.paragraphs = [mock_para]
        mock_docx.return_value = mock_doc

        # Disable LLM in config
        mock_config = MagicMock()
        mock_config.CLOUD_MODEL_ALLOWED = False
        mock_load_config.return_value = mock_config

        claims = self.discernment.extract_claims("dummy.docx")

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].text, "This is a claim that should be extracted heuristically")
        self.assertEqual(claims[0].source_location, "heuristic_body")

    @patch('app.modules.discernment.docx.Document')
    def test_extract_claims_file_error(self, mock_docx):
        mock_docx.side_effect = Exception("File not found")

        claims = self.discernment.extract_claims("dummy.docx")

        self.assertEqual(claims, [])

    @patch('app.modules.discernment.litellm.completion')
    @patch('app.modules.discernment.docx.Document')
    @patch('app.modules.discernment.load_config')
    @patch('app.modules.discernment.os.getenv')
    def test_extract_claims_llm_success(self, mock_getenv, mock_load_config, mock_docx, mock_completion):
        # Setup mocks
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "Some text for LLM."
        mock_doc.paragraphs = [mock_para]
        mock_docx.return_value = mock_doc

        # Enable LLM
        mock_config = MagicMock()
        mock_config.CLOUD_MODEL_ALLOWED = True
        mock_config.LLM_MODEL_NAME = "gpt-4"
        mock_load_config.return_value = mock_config
        mock_getenv.return_value = "fake-api-key"

        # Mock LLM response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '[{"text": "LLM extracted claim", "priority": 1}]'
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_completion.return_value = mock_response

        claims = self.discernment.extract_claims("dummy.docx")

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].text, "LLM extracted claim")
        self.assertEqual(claims[0].source_location, "llm_extracted")

    @patch('app.modules.discernment.litellm.completion')
    @patch('app.modules.discernment.docx.Document')
    @patch('app.modules.discernment.load_config')
    @patch('app.modules.discernment.os.getenv')
    def test_extract_claims_llm_failure(self, mock_getenv, mock_load_config, mock_docx, mock_completion):
        # Setup mocks
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "This is a backup claim."
        mock_doc.paragraphs = [mock_para]
        mock_docx.return_value = mock_doc

        # Enable LLM but make it fail
        mock_config = MagicMock()
        mock_config.CLOUD_MODEL_ALLOWED = True
        mock_load_config.return_value = mock_config
        mock_getenv.return_value = "fake-api-key"

        mock_completion.side_effect = Exception("LLM Error")

        claims = self.discernment.extract_claims("dummy.docx")

        # Should fall back to heuristic
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].text, "This is a backup claim")
        self.assertEqual(claims[0].source_location, "heuristic_body")

if __name__ == '__main__':
    unittest.main()
