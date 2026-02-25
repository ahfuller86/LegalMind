import pytest
from unittest.mock import MagicMock, patch
from app.modules.discernment import Discernment
from app.models import ClaimType, RoutingDecision, Claim
import uuid

@pytest.fixture
def discernment():
    mock_case_context = MagicMock()
    return Discernment(mock_case_context)

def test_citation_router_direct(discernment):
    # Setup claim with citation
    # Need to be careful with Claim model validation if uuid is required
    claim = Claim(
        claim_id=str(uuid.uuid4()),
        text="Refer to 347 U.S. 483.",
        type=ClaimType.FACTUAL,
        source_location="test",
        priority=1,
        routing=RoutingDecision.VERIFY
    )

    discernment.citation_router(claim)

    # 347 U.S. 483 should be detected by eyecite
    assert claim.type == ClaimType.LEGAL_CITATION
    assert claim.routing == RoutingDecision.CITE_CHECK

def test_citation_router_no_match(discernment):
    claim = Claim(
        claim_id=str(uuid.uuid4()),
        text="Just some text.",
        type=ClaimType.FACTUAL,
        source_location="test",
        priority=1,
        routing=RoutingDecision.VERIFY
    )
    discernment.citation_router(claim)
    assert claim.type == ClaimType.FACTUAL
    assert claim.routing == RoutingDecision.VERIFY

@patch("app.modules.discernment.get_citations")
def test_heuristic_integration(mock_get_citations, discernment):
    # Mock get_citations to return something (truthy)
    mock_get_citations.return_value = ["some citation"]

    # Ensure text is long enough > 20 chars
    text = "This is a sentence with a citation that is long enough."
    claims = discernment._heuristic_extract(text)

    assert len(claims) == 1
    assert claims[0].type == ClaimType.LEGAL_CITATION
    assert claims[0].routing == RoutingDecision.CITE_CHECK

    # Verify get_citations was called
    mock_get_citations.assert_called()
