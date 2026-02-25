import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock heavy dependencies before they are imported by app modules
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.utils"] = MagicMock()
sys.modules["chromadb.utils.embedding_functions"] = MagicMock()
sys.modules["litellm"] = MagicMock()

# Handle Pydantic if missing
try:
    import pydantic
except ImportError:
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_copy(self):
            import copy
            new_obj = copy.copy(self)
            new_obj.__dict__ = self.__dict__.copy()
            return new_obj
        def model_dump(self):
            return self.__dict__

    mock_pydantic = MagicMock()
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = mock_pydantic

# Import after mocking
# app.models imports pydantic, so it will use the mock if pydantic is not installed
from app.models import Claim, ClaimType, RoutingDecision, Chunk
from app.modules.inquiry import Inquiry
from app.core.stores import CaseContext

class TestInquiry(unittest.TestCase):
    def setUp(self):
        self.mock_case_context = MagicMock(spec=CaseContext)
        # Avoid real initialization which might rely on files
        self.inquiry = Inquiry(self.mock_case_context)

        # Setup common claim
        self.claim = Claim(
            claim_id="test_claim",
            text="The sky is blue",
            type=ClaimType.FACTUAL,
            source_location="page 1",
            priority=1,
            routing=RoutingDecision.VERIFY
        )

    @patch("app.modules.inquiry.load_config")
    @patch("app.modules.inquiry.litellm")
    def test_contradiction_hunter_with_llm(self, mock_litellm, mock_load_config):
        # Configure mock config
        mock_config = MagicMock()
        mock_config.CLOUD_MODEL_ALLOWED = True
        mock_config.LLM_PROVIDER = "openai"
        mock_load_config.return_value = mock_config

        # Set API key for openai check
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
             # Mock LLM response
             mock_response = MagicMock()
             mock_response.choices = [MagicMock(message=MagicMock(content="The sky is NOT blue"))]
             mock_litellm.completion.return_value = mock_response

             # Mock _dense_search
             mock_chunk = Chunk(
                 chunk_id="c1",
                 segment_ids=[],
                 source="src",
                 page_or_timecode="1",
                 chunk_method="retrieved_dense",
                 text="The sky is red",
                 context_header="",
                 chunk_index=0
             )
             # _dense_search returns List[Tuple[Chunk, float]]
             self.inquiry._dense_search = MagicMock(return_value=[(mock_chunk, 0.9)])

             # Call method
             results = self.inquiry.contradiction_hunter(self.claim)

             # Verify LLM called
             mock_litellm.completion.assert_called_once()

             # Verify _dense_search called with negated text
             args, _ = self.inquiry._dense_search.call_args
             negated_claim = args[0]
             self.assertEqual(negated_claim.text, "The sky is NOT blue")

             # Verify results
             self.assertEqual(len(results), 1)
             self.assertEqual(results[0].chunk_method, "contradiction_hunter")
             self.assertEqual(results[0].text, "The sky is red")

    @patch("app.modules.inquiry.load_config")
    @patch("app.modules.inquiry.litellm")
    def test_contradiction_hunter_fallback(self, mock_litellm, mock_load_config):
        # Configure mock config to disable LLM
        mock_config = MagicMock()
        mock_config.CLOUD_MODEL_ALLOWED = False
        mock_config.LLM_PROVIDER = "openai"
        mock_load_config.return_value = mock_config

        # Mock _dense_search
        mock_chunk = Chunk(
            chunk_id="c1",
            segment_ids=[],
            source="src",
            page_or_timecode="1",
            chunk_method="retrieved_dense",
            text="The sky is red",
            context_header="",
            chunk_index=0
        )
        self.inquiry._dense_search = MagicMock(return_value=[(mock_chunk, 0.9)])

        # Call method
        results = self.inquiry.contradiction_hunter(self.claim)

        # Verify LLM NOT called
        mock_litellm.completion.assert_not_called()

        # Verify _dense_search called with fallback negation
        args, _ = self.inquiry._dense_search.call_args
        negated_claim = args[0]
        self.assertTrue(negated_claim.text.startswith("NOT "))
        self.assertIn("The sky is blue", negated_claim.text)

        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_method, "contradiction_hunter")

if __name__ == "__main__":
    unittest.main()
