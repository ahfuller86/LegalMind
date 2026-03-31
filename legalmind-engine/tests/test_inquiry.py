import sys
import unittest
from unittest.mock import MagicMock

# Mock heavy dependencies
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.utils"] = MagicMock()
sys.modules["chromadb.utils.embedding_functions"] = MagicMock()

# Mock Pydantic if not present
try:
    import pydantic
except ImportError:
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    mock_pydantic = MagicMock()
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = mock_pydantic

# Mock app.core.stores
sys.modules["app.core.stores"] = MagicMock()
sys.modules["app.core.stores"].CaseContext = MagicMock()

from app.modules.inquiry import Inquiry
# We need to import Claim from app.models, which will use the mocked pydantic
from app.models import Claim, ClaimType, RoutingDecision

class TestInquiry(unittest.TestCase):
    def setUp(self):
        self.case_context = MagicMock()
        self.inquiry_instance = Inquiry(self.case_context)

    def test_query_builder_basic(self):
        claim = Claim(
            claim_id="1",
            text="Test claim",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            expected_modality=None,
            entity_anchors=[],
            routing=RoutingDecision.VERIFY
        )

        result = self.inquiry_instance.query_builder(claim)

        self.assertEqual(result["query_text"], "Test claim")
        self.assertIsNone(result["where_filter"])

    def test_query_builder_with_anchors(self):
        claim = Claim(
            claim_id="2",
            text="Test claim",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            expected_modality=None,
            entity_anchors=["Entity1", "Entity2"],
            routing=RoutingDecision.VERIFY
        )

        result = self.inquiry_instance.query_builder(claim)

        self.assertEqual(result["query_text"], "Test claim Entity1 Entity2")
        self.assertIsNone(result["where_filter"])

    def test_modality_filter_video(self):
        claim = Claim(
            claim_id="3",
            text="Video claim",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            expected_modality="video",
            entity_anchors=[],
            routing=RoutingDecision.VERIFY
        )

        result = self.inquiry_instance.query_builder(claim)

        self.assertEqual(result["query_text"], "Video claim")
        self.assertEqual(result["where_filter"], {"modality": "video_transcript"})

    def test_modality_filter_testimony(self):
        claim = Claim(
            claim_id="4",
            text="Testimony claim",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            expected_modality="testimony",
            entity_anchors=[],
            routing=RoutingDecision.VERIFY
        )

        result = self.inquiry_instance.query_builder(claim)

        self.assertEqual(result["query_text"], "Testimony claim")
        self.assertEqual(result["where_filter"], {"modality": "audio_transcript"})

    def test_modality_filter_other(self):
        claim = Claim(
            claim_id="5",
            text="Other claim",
            type=ClaimType.FACTUAL,
            source_location="test",
            priority=1,
            expected_modality="unknown",
            entity_anchors=[],
            routing=RoutingDecision.VERIFY
        )

        result = self.inquiry_instance.query_builder(claim)

        self.assertEqual(result["query_text"], "Other claim")
        self.assertIsNone(result["where_filter"])

if __name__ == '__main__':
    unittest.main()
