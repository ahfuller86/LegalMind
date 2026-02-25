import unittest
from unittest.mock import MagicMock, patch
import sys
import uuid
import importlib

# --- Mock Classes ---

class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump_json(self):
        return "{}"

class MockModality:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

class MockEvidenceSegment(MockBaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'modality' in kwargs and not hasattr(kwargs['modality'], 'value'):
             pass

class MockChunk(MockBaseModel):
    pass

# --- Test Class ---

class TestStructuring(unittest.TestCase):

    def setUp(self):
        # Create mocks for dependencies
        self.mock_pydantic = MagicMock()
        self.mock_pydantic.BaseModel = MockBaseModel
        self.mock_pydantic.Field = MagicMock(return_value=None)

        self.mock_app_models = MagicMock()
        self.mock_app_models.EvidenceSegment = MockEvidenceSegment
        self.mock_app_models.Chunk = MockChunk
        self.mock_app_models.Modality = MagicMock()
        self.mock_app_models.Modality.PDF_TEXT = MockModality("pdf_text")

        self.mock_stores = MagicMock()

        # Patch sys.modules
        self.modules_patcher = patch.dict(sys.modules, {
            "pydantic": self.mock_pydantic,
            "app.models": self.mock_app_models,
            "app.core.stores": self.mock_stores
        })
        self.modules_patcher.start()

        # Import Structuring ensuring a fresh import
        # We need to remove it from sys.modules if it's there to force re-import with our mocks
        if 'app.modules.structuring' in sys.modules:
            del sys.modules['app.modules.structuring']

        try:
            from app.modules.structuring import Structuring
            self.StructuringClass = Structuring
        except ImportError:
            self.fail("Failed to import Structuring module even with mocks in place")

        # Setup CaseContext mock
        self.mock_case_context = MagicMock()
        self.mock_case_context.index.get_chunk_count.return_value = 0

        # Instantiate Structuring
        self.structuring = self.StructuringClass(self.mock_case_context)

    def tearDown(self):
        self.modules_patcher.stop()
        # Clean up to prevent side effects
        if 'app.modules.structuring' in sys.modules:
            del sys.modules['app.modules.structuring']

    def test_structural_chunker_basic(self):
        """Test basic paragraph splitting"""
        # Ensure Modality value is accessible
        # MockEvidenceSegment uses MockBaseModel which just sets attrs from kwargs
        segment = MockEvidenceSegment(
            segment_id="seg1",
            source_asset_id="asset1",
            location="page_1",
            modality=MockModality("pdf_text"),
            text="First paragraph.\n\nSecond paragraph.",
            extraction_method="ocr"
        )

        chunks = self.structuring.structural_chunker([segment])

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].text, "First paragraph.")
        self.assertEqual(chunks[1].text, "Second paragraph.")
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[1].chunk_index, 1)
        self.assertEqual(chunks[0].segment_ids, ["seg1"])

        # Verify chunks added to index
        self.mock_case_context.index.add_chunks.assert_called_once()
        call_args = self.mock_case_context.index.add_chunks.call_args[0][0]
        self.assertEqual(len(call_args), 2)

    def test_structural_chunker_empty_lines(self):
        """Test splitting with multiple newlines and whitespace"""
        segment = MockEvidenceSegment(
            segment_id="seg2",
            source_asset_id="asset2",
            location="page_2",
            modality=MockModality("pdf_text"),
            text="Para 1\n\n\n\nPara 2\n\n   \n\nPara 3",
            extraction_method="ocr"
        )

        chunks = self.structuring.structural_chunker([segment])

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].text, "Para 1")
        self.assertEqual(chunks[1].text, "Para 2")
        self.assertEqual(chunks[2].text, "Para 3")

    def test_structural_chunker_index_increment(self):
        """Test chunk index increment across multiple segments"""
        self.mock_case_context.index.get_chunk_count.return_value = 10

        seg1 = MockEvidenceSegment(
            segment_id="s1", source_asset_id="a", location="l", modality=MockModality("m"),
            text="P1", extraction_method="e"
        )
        seg2 = MockEvidenceSegment(
            segment_id="s2", source_asset_id="a", location="l", modality=MockModality("m"),
            text="P2\n\nP3", extraction_method="e"
        )

        chunks = self.structuring.structural_chunker([seg1, seg2])

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].chunk_index, 10)
        self.assertEqual(chunks[1].chunk_index, 11)
        self.assertEqual(chunks[2].chunk_index, 12)

    def test_sentence_chunker_basic(self):
        """Test basic sentence splitting"""
        text = "This is a sentence. This is another one."
        sentences = self.structuring.sentence_chunker(text)
        self.assertEqual(sentences, ["This is a sentence.", "This is another one."])

    def test_sentence_chunker_abbreviations(self):
        """Test sentence splitting with abbreviations"""
        cases = [
            ("Smith v. Jones", ["Smith v. Jones"]),
            ("See id. at 5.", ["See id. at 5."]),
            ("The U.S. is large.", ["The U.S. is large."]),
            ("e.g. valid.", ["e.g. valid."]),
            ("Refer to No. 5.", ["Refer to No. 5."]),
            ("Mixed case. Smith v. Jones. End.", ["Mixed case.", "Smith v. Jones.", "End."])
        ]

        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.structuring.sentence_chunker(text), expected)

    def test_sentence_chunker_newlines(self):
        """Test that newlines are replaced by spaces"""
        text = "Sentence one.\nSentence two."
        sentences = self.structuring.sentence_chunker(text)
        self.assertEqual(sentences, ["Sentence one.", "Sentence two."])

        text2 = "Split\nsentence."
        sentences2 = self.structuring.sentence_chunker(text2)
        self.assertEqual(sentences2, ["Split sentence."])

if __name__ == '__main__':
    unittest.main()
