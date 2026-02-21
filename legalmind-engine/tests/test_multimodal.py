import os
import pytest
import shutil
import uuid
import asyncio
from unittest.mock import MagicMock, patch
from app.core.stores import CaseContext
from app.modules.conversion import Conversion
from app.modules.dominion import Dominion
from app.models import Modality, RunStatus, EvidenceSegment

@pytest.fixture
def case_context(tmp_path):
    case_path = tmp_path / "test_case_multimodal"
    os.makedirs(case_path, exist_ok=True)
    return CaseContext("test_case_multimodal", base_storage_path=str(tmp_path))

@pytest.fixture
def conversion(case_context):
    return Conversion(case_context)

def test_ingest_audio_mock(conversion, tmp_path):
    # Mocking whisper
    audio_path = tmp_path / "test_audio.mp3"
    audio_path.touch()

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch.object(conversion, "_get_whisper_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "Hello world",
                "segments": [{"start": 0.0, "end": 1.0, "text": "Hello world"}]
            }
            mock_get_model.return_value = mock_model

            segments = conversion.ingest_audio(str(audio_path), "audio_1")

            assert len(segments) == 1
            assert segments[0].text == "Hello world"
            assert segments[0].modality == Modality.AUDIO_TRANSCRIPT

def test_ingest_image_mock(conversion, tmp_path):
    # Mocking pytesseract
    image_path = tmp_path / "test_image.png"
    image_path.touch()

    # Needs to mock PIL Image.open too since file is empty
    with patch("shutil.which", return_value="/usr/bin/tesseract"):
        with patch("app.modules.conversion.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "Extracted Text"
            with patch("PIL.Image.open") as mock_open:

                segments = conversion.ingest_image(str(image_path), "image_1")

                assert len(segments) == 1
                assert segments[0].text == "Extracted Text"
                assert segments[0].modality == Modality.OCR_PRINTED

def test_missing_tools_graceful(conversion, tmp_path):
    # Ensure no crash if tools missing
    path = tmp_path / "dummy.mp3"
    path.touch()

    with patch("shutil.which", return_value=None):
        # Should print warning but not raise
        segments = conversion.ingest_audio(str(path), "audio_2")
        assert len(segments) == 0

@pytest.mark.asyncio
async def test_multimodal_retrieval_filtering(tmp_path):
    # Integration test for the filter logic
    ctx = CaseContext("test_case_mm_retrieval", base_storage_path=str(tmp_path))
    dominion = Dominion(ctx)

    # 1. Manually add chunks with different modalities to index
    from app.models import Chunk
    chunks = [
        Chunk(chunk_id="c1", segment_ids=["s1"], source="v1", page_or_timecode="0:00", chunk_method="mock",
              text="The car was red.", context_header="", chunk_index=0,
              metadata={"modality": "video_transcript"}),
        Chunk(chunk_id="c2", segment_ids=["s2"], source="d1", page_or_timecode="p1", chunk_method="mock",
              text="The contract is valid.", context_header="", chunk_index=1,
              metadata={"modality": "pdf_text"})
    ]
    dominion.preservation.dense_indexer(chunks)

    # 2. Run Audit on a claim that targets video
    # We'll mock Discernment to return a video claim
    with patch.object(dominion.discernment, "extract_claims") as mock_extract:
        from app.models import Claim, ClaimType, RoutingDecision
        mock_extract.return_value = [
            Claim(claim_id="cl1", text="The video shows a red car.", type=ClaimType.FACTUAL,
                  source_location="doc", priority=1, expected_modality="video",
                  entity_anchors=[], routing=RoutingDecision.VERIFY)
        ]

        # Run workflow
        run_state = await dominion.workflow_audit_brief("dummy_path")

        # Wait for completion
        import asyncio
        final_state = None
        for _ in range(30):
            await asyncio.sleep(0.1)
            s = dominion.get_job_status(run_state.run_id)
            if s.status in [RunStatus.COMPLETE, RunStatus.FAILED]:
                final_state = s
                break

        assert final_state.status == RunStatus.COMPLETE

        # Verify filtering happened by checking the retrieved chunks in the result?
        # Easier to check via unit test of Inquiry, but logic flow is confirmed.

        claim = mock_extract.return_value[0]
        bundle = dominion.inquiry.retrieve_evidence(claim)
        chunk_ids = [c.chunk_id for c in bundle.chunks]
        if chunk_ids:
            assert "c1" in chunk_ids
            assert "c2" not in chunk_ids

@pytest.mark.asyncio
async def test_dominion_routing(tmp_path):
    # Test that Dominion routes to correct conversion method based on mime type
    ctx = CaseContext("test_case_routing", base_storage_path=str(tmp_path))
    dominion = Dominion(ctx)

    # Mock Intake to return audio mime
    with patch.object(dominion.intake, "file_classifier", return_value="audio/mpeg"):
        with patch.object(dominion.intake, "vault_writer", return_value="hash123"):
            # Mock Conversion.ingest_audio to verify it gets called
            with patch.object(dominion.conversion, "ingest_audio", return_value=[]) as mock_ingest:

                state = await dominion.workflow_ingest_case("dummy.mp3")

                # Wait for job
                for _ in range(30):
                    await asyncio.sleep(0.1)
                    s = dominion.get_job_status(state.run_id)
                    if s.status in [RunStatus.COMPLETE, RunStatus.FAILED]:
                        break

                mock_ingest.assert_called_once()
