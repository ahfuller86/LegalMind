import pytest
from unittest.mock import MagicMock, patch
from app.modules.adjudication import Adjudication
from app.core.stores import CaseContext
from app.models import (
    Claim, ClaimType, RoutingDecision, EvidenceBundle, Chunk, RetrievalMode,
    VerificationStatus, ConfidenceLevel
)

@pytest.fixture
def case_context(tmp_path):
    return CaseContext("test_case_adj", base_storage_path=str(tmp_path))

@pytest.fixture
def adjudication(case_context):
    return Adjudication(case_context)

@pytest.fixture
def sample_claim():
    return Claim(
        claim_id="c1",
        text="The defendant was present at the scene.",
        type=ClaimType.FACTUAL,
        source_location="Brief p.10",
        priority=1,
        routing=RoutingDecision.VERIFY
    )

@pytest.fixture
def sample_bundle():
    chunk = Chunk(
        chunk_id="chk1",
        segment_ids=["seg1"],
        source="test.pdf",
        page_or_timecode="1",
        chunk_method="test",
        text="Witness A testified that the defendant was present at the scene.",
        context_header="",
        chunk_index=0
    )
    return EvidenceBundle(
        bundle_id="b1",
        claim_id="c1",
        chunks=[chunk],
        retrieval_scores=[0.5],
        retrieval_mode=RetrievalMode.SEMANTIC,
        modality_filter_applied=False
    )

def test_verify_claim_skeptical_heuristic(adjudication, sample_claim, sample_bundle):
    # Force heuristic by setting config.CLOUD_MODEL_ALLOWED to False
    adjudication.config.CLOUD_MODEL_ALLOWED = False

    finding = adjudication.verify_claim_skeptical(sample_claim, sample_bundle)

    assert finding.claim_id == sample_claim.claim_id
    assert finding.status == VerificationStatus.SUPPORTED # Score 0.5 < 1.0
    assert "Heuristic verification used" in finding.warnings

def test_verify_claim_skeptical_llm_success(adjudication, sample_claim, sample_bundle):
    adjudication.config.CLOUD_MODEL_ALLOWED = True
    adjudication.config.LLM_PROVIDER = "openai"

    # Mock os.getenv to allow LLM execution
    with patch("os.getenv", return_value="dummy_key"):
        # Mock litellm.completion
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"status": "Supported", "reasoning": "Evidence matches claim", "quote": "defendant was present"}'))]
            )

            finding = adjudication.verify_claim_skeptical(sample_claim, sample_bundle)

            assert finding.status == VerificationStatus.SUPPORTED
            assert finding.justification.elements_supported == ["Evidence matches claim"]
            assert finding.quotes_with_provenance == ["defendant was present"]

def test_verify_claim_skeptical_llm_json_failure_fallback(adjudication, sample_claim, sample_bundle):
    adjudication.config.CLOUD_MODEL_ALLOWED = True
    adjudication.config.LLM_PROVIDER = "openai"

    with patch("os.getenv", return_value="dummy_key"):
        with patch("litellm.completion") as mock_completion:
            # Return invalid JSON
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='Not JSON'))]
            )

            finding = adjudication.verify_claim_skeptical(sample_claim, sample_bundle)

            # Should fallback to heuristic
            assert "Heuristic verification used" in finding.warnings
            assert finding.status == VerificationStatus.SUPPORTED # Because score is 0.5

def test_verify_claim_skeptical_llm_exception_fallback(adjudication, sample_claim, sample_bundle):
    adjudication.config.CLOUD_MODEL_ALLOWED = True
    adjudication.config.LLM_PROVIDER = "openai"

    with patch("os.getenv", return_value="dummy_key"):
        with patch("litellm.completion") as mock_completion:
            mock_completion.side_effect = Exception("API Error")

            finding = adjudication.verify_claim_skeptical(sample_claim, sample_bundle)

            # Should fallback to heuristic
            assert "Heuristic verification used" in finding.warnings
