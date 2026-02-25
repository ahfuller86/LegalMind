import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# --- MOCKING DEPENDENCIES ---
mock_pydantic = MagicMock()
class MockBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    def dict(self):
        return self.__dict__
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = MagicMock(return_value=None)

sys.modules["pydantic"] = mock_pydantic
sys.modules["pdfplumber"] = MagicMock()
sys.modules["docx"] = MagicMock()
sys.modules["whisper"] = MagicMock()
sys.modules["ffmpeg"] = MagicMock()
sys.modules["pdf2image"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["litellm"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
# --- END MOCKING ---

# Now we can try to import
# We need to make sure the app path is in sys.path
sys.path.insert(0, os.path.join(os.getcwd(), "legalmind-engine"))

# Also need to mock app.core.config because load_config is called
sys.modules["app.core.config"] = MagicMock()

from app.models import EvidenceSegment, Modality
from app.modules.conversion import Conversion

@pytest.fixture
def case_context(tmp_path):
    # Setup a mock CaseContext
    vault = MagicMock()
    vault.vault_path = str(tmp_path / "vault")
    os.makedirs(vault.vault_path, exist_ok=True)

    ledger = MagicMock()

    ctx = MagicMock()
    ctx.vault = vault
    ctx.ledger = ledger
    return ctx

@pytest.fixture
def conversion(case_context):
    return Conversion(case_context)

def test_refine_transcription_uses_tempfile_securely(conversion, case_context):
    segment_id = "test-uuid-5678"
    asset_id = "asset-456"

    source_file = os.path.join(case_context.vault.vault_path, asset_id)
    with open(source_file, "w") as f:
        f.write("dummy audio content")

    segment = EvidenceSegment(
        segment_id=segment_id,
        source_asset_id=asset_id,
        modality=Modality.AUDIO_TRANSCRIPT if hasattr(Modality, 'AUDIO_TRANSCRIPT') else 'audio_transcript',
        location="0-1",
        text="draft text",
        confidence=0.5,
        extraction_method="whisper-fast",
        derived=False,
        metadata={
            "timestamp_start": 0.0,
            "timestamp_end": 1.0,
            "transcription_quality": "draft"
        }
    )
    segment.warnings = []

    with patch("app.modules.conversion.ffmpeg") as mock_ffmpeg:
        with patch("app.modules.conversion.WhisperModelManager") as mock_mgr_cls:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {"text": "refined text"}
            mock_mgr_cls.get_instance.return_value.get_model.return_value = mock_model

            with patch("app.modules.conversion.os.remove") as mock_remove:
                conversion.refine_transcription(segment)

                # If start/duration are provided, ffmpeg should be called
                mock_ffmpeg.input.return_value.output.assert_called()
                args, kwargs = mock_ffmpeg.input.return_value.output.call_args
                used_path = args[0]

                # After fix, this should NOT be /tmp/test-uuid-5678.wav
                assert used_path != f"/tmp/{segment_id}.wav"
                assert segment_id not in used_path
                # It should be a system temp path
                import tempfile
                assert used_path.startswith(tempfile.gettempdir())

                # Verify cleanup was called on the CORRECT path
                mock_remove.assert_called_with(used_path)
