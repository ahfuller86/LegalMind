import sys
import unittest
from unittest.mock import MagicMock, patch

# --- Mocks Setup ---

# Mock Pydantic
class MockBaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def dict(self):
        return self.__dict__
    def model_dump(self):
        return self.__dict__
    class Config:
        arbitrary_types_allowed = True

class MockField:
    def __init__(self, *args, **kwargs): pass

mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MockField
sys.modules["pydantic"] = mock_pydantic

# Mock ChromaDB
mock_chromadb = MagicMock()
sys.modules["chromadb"] = mock_chromadb
sys.modules["chromadb.utils"] = MagicMock()
sys.modules["chromadb.utils.embedding_functions"] = MagicMock()

# Mock sentence_transformers (initially mocked to allow import)
mock_sentence_transformers = MagicMock()
sys.modules["sentence_transformers"] = mock_sentence_transformers

# Mock app modules
mock_stores = MagicMock()
sys.modules["app.core.stores"] = mock_stores

mock_models = MagicMock()
mock_models.BaseModel = MockBaseModel
mock_models.Claim = MagicMock()
mock_models.Chunk = MagicMock()
mock_models.EvidenceBundle = MagicMock()
mock_models.RetrievalMode = MagicMock()
sys.modules["app.models"] = mock_models

# --- Import System Under Test ---

# We need to make sure Inquiry is imported after mocks are set
if "app.modules.inquiry" in sys.modules:
    del sys.modules["app.modules.inquiry"]

from app.modules.inquiry import Inquiry

class TestInquiryReranker(unittest.TestCase):
    def setUp(self):
        self.mock_case_context = MagicMock()
        # Mock index path for __init__ or methods that use it
        self.mock_case_context.index.index_path = "/tmp/test_index"
        self.inquiry = Inquiry(self.mock_case_context)

    @patch("sentence_transformers.CrossEncoder")
    def test_reranker_success(self, mock_cross_encoder_cls):
        """Test reranker successfully re-orders results based on CrossEncoder scores."""
        # Setup mock model instance
        mock_model = MagicMock()
        mock_cross_encoder_cls.return_value = mock_model

        # Prepare inputs
        chunk1 = MagicMock()
        chunk1.chunk_id = "c1"
        chunk1.text = "chunk text one"

        chunk2 = MagicMock()
        chunk2.chunk_id = "c2"
        chunk2.text = "chunk text two"

        claim = MagicMock()
        claim.text = "query claim"

        # Initial results: c1 (0.5), c2 (0.4)
        results = [(chunk1, 0.5), (chunk2, 0.4)]

        # Mock predict return values
        # Assume model gives higher score to c2 (e.g., 0.9) than c1 (e.g., 0.1)
        # Note: predict inputs will be [[query, c1.text], [query, c2.text]]
        mock_model.predict.return_value = [0.1, 0.9]

        # Execute
        reranked = self.inquiry.reranker(results, claim)

        # Verify
        mock_cross_encoder_cls.assert_called() # Should initialize model
        mock_model.predict.assert_called()

        # Check call args
        call_args = mock_model.predict.call_args[0][0]
        self.assertEqual(len(call_args), 2)
        self.assertEqual(call_args[0], ["query claim", "chunk text one"])
        self.assertEqual(call_args[1], ["query claim", "chunk text two"])

        # Check result order: c2 should be first because score 0.9 > 0.1
        self.assertEqual(len(reranked), 2)
        self.assertEqual(reranked[0][0].chunk_id, "c2")
        self.assertEqual(reranked[0][1], 0.9)
        self.assertEqual(reranked[1][0].chunk_id, "c1")
        self.assertEqual(reranked[1][1], 0.1)

    def test_reranker_missing_dependency(self):
        """Test reranker behaves gracefully when sentence_transformers is missing."""
        # We need to simulate ImportError when importing CrossEncoder
        # Since we mocked sys.modules["sentence_transformers"], we need to adjust it

        # This is tricky because we imported Inquiry which might have imported it?
        # Actually Inquiry currently doesn't import CrossEncoder.
        # But if we change Inquiry to import inside method, we can mock it here.

        with patch.dict(sys.modules, {"sentence_transformers": None}):
            # If we try to import inside reranker, it should raise ImportError

            chunk1 = MagicMock()
            chunk1.chunk_id = "c1"
            results = [(chunk1, 0.5)]
            claim = MagicMock()
            claim.text = "query"

            reranked = self.inquiry.reranker(results, claim)

            # Should return original results unmodified
            self.assertEqual(reranked, results)

    def test_reranker_empty_results(self):
        """Test reranker with empty results list."""
        results = []
        claim = MagicMock()
        reranked = self.inquiry.reranker(results, claim)
        self.assertEqual(reranked, [])

if __name__ == "__main__":
    unittest.main()
