import os
import json
import pytest
from unittest.mock import MagicMock
from app.modules.chronicle import Chronicle
from app.core.stores import CaseContext
from app.models import (
    VerificationFinding, CitationFinding, GateResult,
    VerificationStatus, CitationStatus, FilingRecommendation, ConfidenceLevel, Justification
)
from datetime import datetime

# Dummy data
def get_dummy_data():
    findings = [
        VerificationFinding(
            claim_id="claim_1",
            status=VerificationStatus.SUPPORTED,
            justification=Justification(
                elements_supported=["element 1"],
                elements_missing=[],
                contradictions=[]
            ),
            quotes_with_provenance=["Quote 1"],
            evidence_refs=["ref1"],
            confidence=ConfidenceLevel.HIGH
        ),
        VerificationFinding(
            claim_id="claim_2",
            status=VerificationStatus.CONTRADICTED,
            justification=Justification(
                elements_supported=[],
                elements_missing=[],
                contradictions=["contradiction 1"]
            ),
            quotes_with_provenance=["Quote 2"],
            evidence_refs=["ref2"],
            confidence=ConfidenceLevel.MEDIUM
        )
    ]

    citation_findings = [
        CitationFinding(
            citation_text="347 U.S. 483",
            normalized_form="347 U.S. 483",
            status=CitationStatus.VERIFIED,
            confidence=0.95,
            case_details={"name": "Brown v. Board of Education", "date": "1954", "court": "SCOTUS", "url": "http://..."},
            reconciliation_notes="Verified via CourtListener",
            source_pass="api"
        ),
        CitationFinding(
            citation_text="123 Fake St.",
            normalized_form="123 Fake St.",
            status=CitationStatus.NOT_FOUND,
            confidence=0.1,
            case_details={},
            reconciliation_notes="Not found",
            source_pass="local"
        )
    ]

    gate_result = GateResult(
        document_id="doc_1",
        filing_recommendation=FilingRecommendation.REVIEW_REQUIRED,
        risk_score=25.0,
        citation_summary={"verified": 1, "not_found": 1},
        claim_summary={"supported": 1, "contradicted": 1},
        config_snapshot={"model": "gpt-4"},
        timestamp=datetime.now()
    )

    return findings, citation_findings, gate_result

@pytest.fixture
def mock_case_context(tmp_path):
    mock = MagicMock(spec=CaseContext)
    mock.base_path = str(tmp_path)
    return mock

def test_quality_dashboard(mock_case_context):
    chronicle = Chronicle(mock_case_context)
    findings, citation_findings, gate_result = get_dummy_data()

    # Call quality_dashboard
    dashboard_path = chronicle.quality_dashboard(findings, citation_findings, gate_result)

    # Check if files were created
    json_path = os.path.join(mock_case_context.base_path, "dashboard.json")
    html_path = os.path.join(mock_case_context.base_path, "dashboard.html")

    assert os.path.exists(json_path), "dashboard.json should be created"
    assert os.path.exists(html_path), "dashboard.html should be created"
    assert dashboard_path == html_path

    # Verify JSON content
    with open(json_path, 'r') as f:
        data = json.load(f)
        assert data['total_claims'] == 2
        assert data['supported_claims'] == 1
        assert data['contradicted_claims'] == 1
        assert data['total_citations'] == 2
        assert data['verified_citations'] == 1
        assert data['risk_score'] == 25.0
        assert data['filing_recommendation'] == "REVIEW_REQUIRED"

    # Verify HTML content (simple check)
    with open(html_path, 'r') as f:
        content = f.read()
        assert "Quality Dashboard" in content
        assert "Risk Score:" in content
        assert "25.0" in content
        assert "Supported" in content
