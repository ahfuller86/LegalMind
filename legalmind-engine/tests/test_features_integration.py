
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import shutil
import importlib

class TestFeatureIntegration(unittest.TestCase):

    def setUp(self):
        self.test_dir = "/tmp/legalmind_test_integration"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # --- 1. Whisper Robustness ---
    def test_whisper_singleton(self):
        # Mock dependencies
        with patch.dict(sys.modules, {
            "whisper": MagicMock(),
            "pdfplumber": MagicMock(),
            "docx": MagicMock(),
            "pytesseract": MagicMock(),
            "ffmpeg": MagicMock(),
            "pdf2image": MagicMock()
        }):
            if "app.modules.conversion" in sys.modules:
                del sys.modules["app.modules.conversion"]

            from app.modules.conversion import WhisperModelManager

            m1 = WhisperModelManager.get_instance()
            m2 = WhisperModelManager.get_instance()
            self.assertIs(m1, m2)

    def test_whisper_missing(self):
        # Simulate whisper not installed
        with patch.dict(sys.modules):
            # To simulate ImportError, we can remove it from sys.modules and ensure finder fails,
            # or map it to None (which causes ModuleNotFoundError in recent Pythons)
            sys.modules["whisper"] = None

            # Mock others to avoid unrelated errors
            sys.modules["pdfplumber"] = MagicMock()
            sys.modules["docx"] = MagicMock()
            sys.modules["pytesseract"] = MagicMock()
            sys.modules["ffmpeg"] = MagicMock()
            sys.modules["pdf2image"] = MagicMock()

            if "app.modules.conversion" in sys.modules:
                del sys.modules["app.modules.conversion"]

            # This import should succeed but set whisper=None internally
            from app.modules.conversion import WhisperModelManager

            manager = WhisperModelManager.get_instance()
            model = manager.get_model("tiny")
            self.assertIsNone(model)

    def test_whisper_load_error(self):
        # Simulate load_model failure
        mock_whisper = MagicMock()
        mock_whisper.load_model.side_effect = Exception("Load failed")

        with patch.dict(sys.modules, {
            "whisper": mock_whisper,
            "pdfplumber": MagicMock(),
            "docx": MagicMock(),
            "pytesseract": MagicMock(),
            "ffmpeg": MagicMock(),
            "pdf2image": MagicMock()
        }):
            if "app.modules.conversion" in sys.modules:
                del sys.modules["app.modules.conversion"]

            from app.modules.conversion import WhisperModelManager

            manager = WhisperModelManager.get_instance()
            # Reset internal state just in case (though module reload should clear singleton class attributes if logic is standard?)
            # Wait, singleton is a class attribute `_instance`. Reloading the module redefines the class, so `_instance` is None.
            # So we get a fresh instance.

            model = manager.get_model("tiny")
            self.assertIsNone(model)

    # --- 2. Evidence Register Optimization (File Lock) ---
    def test_intake_file_lock(self):
        # We need to import Intake. It uses CaseContext.
        # We can mock CaseContext or use real one.
        # Since Intake imports `fcntl` directly, we can patch `fcntl` in sys.modules OR `app.modules.intake.fcntl`

        with patch.dict(sys.modules, {"app.core.stores": MagicMock()}):
            if "app.modules.intake" in sys.modules:
                del sys.modules["app.modules.intake"]

            from app.modules.intake import file_lock
            import fcntl

            lock_path = os.path.join(self.test_dir, "test.lock")

            # We patch fcntl.flock on the module we just imported or global?
            # Since `from app.modules.intake import file_lock` imports the function,
            # and that function uses `fcntl` from the module scope.

            # Let's patch `app.modules.intake.fcntl.flock`
            with patch("app.modules.intake.fcntl.flock") as mock_flock:
                with file_lock(lock_path):
                    pass
                self.assertTrue(mock_flock.called)

    # --- 3. Chunk Counting Optimization ---
    def test_chunk_counting_buffered(self):
        # RetrievalIndex uses real IO. We don't need heavy mocks.
        # Just need to ensure app.core.stores is clean.

        if "app.core.stores" in sys.modules:
            del sys.modules["app.core.stores"]

        from app.core.stores import RetrievalIndex

        chunks_file = os.path.join(self.test_dir, "chunks.jsonl")
        with open(chunks_file, "w") as f:
            for i in range(5000):
                f.write(f'{{"id": {i}}}\n')

        idx = RetrievalIndex("test_case", self.test_dir)
        idx.chunks_file = chunks_file

        count = idx.get_chunk_count()
        self.assertEqual(count, 5000)

    # --- 4. DOCX Granularity ---
    def test_docx_granularity(self):
        # Mock docx
        mock_docx_module = MagicMock()
        mock_doc_cls = MagicMock()
        mock_docx_module.Document = mock_doc_cls

        mock_doc = MagicMock()
        p1 = MagicMock(); p1.text = "Para 1"
        p2 = MagicMock(); p2.text = "Para 2"
        mock_doc.paragraphs = [p1, p2]
        mock_doc_cls.return_value = mock_doc

        with patch.dict(sys.modules, {
            "docx": mock_docx_module,
            "whisper": MagicMock(),
            "pdfplumber": MagicMock(),
            "pytesseract": MagicMock(),
            "ffmpeg": MagicMock(),
            "pdf2image": MagicMock()
        }):
            if "app.modules.conversion" in sys.modules:
                del sys.modules["app.modules.conversion"]

            from app.modules.conversion import Conversion

            # We need a dummy CaseContext for Conversion init
            mock_case_context = MagicMock()
            conversion = Conversion(mock_case_context)

            segments = conversion.ingest_docx("dummy.docx", "asset_1")

            self.assertEqual(len(segments), 2)
            self.assertEqual(segments[0].text, "Para 1")
            self.assertEqual(segments[0].location, "para_1")

if __name__ == '__main__':
    unittest.main()
