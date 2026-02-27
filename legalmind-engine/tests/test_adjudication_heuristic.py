import sys
from unittest.mock import MagicMock

# --- CONDITIONAL MOCKING START ---
# This ensures we don't break environments where dependencies are installed,
# but allow running in limited environments (like this sandbox).

try:
    import pydantic
except ImportError:
    # Mock pydantic if missing
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self):
            return self.__dict__

        def json(self):
            return str(self.__dict__)

    mock_pydantic = MagicMock()
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.Field = MagicMock(return_value=None)
    sys.modules["pydantic"] = mock_pydantic
    sys.modules["pydantic_settings"] = MagicMock()

# Check other dependencies
try:
    import litellm
except ImportError:
    sys.modules["litellm"] = MagicMock()

try:
    import chromadb
except ImportError:
    sys.modules["chromadb"] = MagicMock()

try:
    import sentence_transformers
except ImportError:
    sys.modules["sentence_transformers"] = MagicMock()

try:
    import rank_bm25
except ImportError:
    sys.modules["rank_bm25"] = MagicMock()

try:
    import eyecite
except ImportError:
    sys.modules["eyecite"] = MagicMock()

try:
    import weasyprint
except ImportError:
    sys.modules["weasyprint"] = MagicMock()

try:
    import pdf2image
except ImportError:
    sys.modules["pdf2image"] = MagicMock()

# --- MOCKING END ---

import pytest
from app.modules.adjudication import Adjudication
from app.core.stores import CaseContext
from app.models import (
    Claim, ClaimType, RoutingDecision, EvidenceBundle, Chunk, RetrievalMode,
    VerificationStatus, ConfidenceLevel
)

@pytest.fixture
def adjudication():
    # Mock CaseContext to avoid file system operations
    mock_case_context = MagicMock(spec=CaseContext)
    mock_case_context.audit_log = MagicMock()
    return Adjudication(mock_case_context)

@pytest.fixture
def sample_claim():
    # Create a Claim instance.
    # If pydantic is mocked, MockBaseModel handles this.
    # If pydantic is real, standard init.
    return Claim(
        claim_id="c1",
        text="Test Claim",
        type=ClaimType.FACTUAL,
        source_location="Brief p.1",
        priority=1,
        routing=RoutingDecision.VERIFY
    )

def create_bundle(scores, chunks_count=1):
    chunks = []
    if chunks_count > 0:
        chunks = [
            Chunk(
                chunk_id=f"chk{i}",
                segment_ids=[f"seg{i}"],
                source="test.pdf",
                page_or_timecode="1",
                chunk_method="test",
                text=f"Chunk text {i}",
                context_header="",
                chunk_index=i
            ) for i in range(chunks_count)
        ]

    return EvidenceBundle(
        bundle_id="b1",
        claim_id="c1",
        chunks=chunks,
        retrieval_scores=scores,
        retrieval_mode=RetrievalMode.SEMANTIC,
        modality_filter_applied=False
    )

@pytest.mark.parametrize("score, expected_status, expected_confidence", [
    (0.0, VerificationStatus.SUPPORTED, ConfidenceLevel.MEDIUM),
    (0.999, VerificationStatus.SUPPORTED, ConfidenceLevel.MEDIUM),
    (1.0, VerificationStatus.PARTIALLY_SUPPORTED, ConfidenceLevel.LOW),
    (1.25, VerificationStatus.PARTIALLY_SUPPORTED, ConfidenceLevel.LOW),
    (1.499, VerificationStatus.PARTIALLY_SUPPORTED, ConfidenceLevel.LOW),
    (1.5, VerificationStatus.NOT_SUPPORTED, ConfidenceLevel.LOW),
    (2.0, VerificationStatus.NOT_SUPPORTED, ConfidenceLevel.LOW),
])
def test_heuristic_verify_thresholds(adjudication, sample_claim, score, expected_status, expected_confidence):
    """
    Test heuristic verification logic against score thresholds.
    Thresholds:
    - < 1.0: SUPPORTED
    - 1.0 <= x < 1.5: PARTIALLY_SUPPORTED
    - >= 1.5: NOT_SUPPORTED
    """
    bundle = create_bundle(scores=[score])
    finding = adjudication._heuristic_verify(sample_claim, bundle)

    assert finding.status == expected_status
    assert finding.confidence == expected_confidence

    if expected_status == VerificationStatus.SUPPORTED:
        assert finding.quotes_with_provenance == ["Chunk text 0"]
    else:
        assert finding.quotes_with_provenance == []

def test_heuristic_verify_no_scores(adjudication, sample_claim):
    """Test behavior when retrieval_scores is empty but chunks exist."""
    bundle = create_bundle(scores=[], chunks_count=1)

    finding = adjudication._heuristic_verify(sample_claim, bundle)

    # Should log error and return default NOT_SUPPORTED
    adjudication.case_context.audit_log.log_event.assert_called_with(
        "Adjudication", "heuristic_error",
        {"error": "No scores for chunks", "claim_id": sample_claim.claim_id}
    )
    assert finding.status == VerificationStatus.NOT_SUPPORTED
    assert finding.confidence == ConfidenceLevel.LOW

def test_heuristic_verify_no_chunks(adjudication, sample_claim):
    """Test behavior when no chunks are found."""
    bundle = create_bundle(scores=[], chunks_count=0)

    finding = adjudication._heuristic_verify(sample_claim, bundle)

    assert finding.status == VerificationStatus.NOT_SUPPORTED
    assert finding.confidence == ConfidenceLevel.LOW
    assert finding.quotes_with_provenance == []
