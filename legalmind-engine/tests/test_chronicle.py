import os
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.modules.chronicle import Chronicle
from app.core.stores import CaseContext
from app.models import (
    VerificationFinding, CitationFinding, GateResult,
    VerificationStatus, CitationStatus, ConfidenceLevel,
    FilingRecommendation, Chunk, Justification
)

@pytest.fixture
def mock_case_context(tmp_path):
    # Mock CaseContext to use tmp_path as base_path
    context = MagicMock(spec=CaseContext)
    context.base_path = str(tmp_path)
    return context

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.LLM_PROVIDER = "test_provider"
    config.EXPORT_RAW_EVIDENCE = True
    return config

def test_transparency_writer(mock_case_context, mock_config):
    with patch("app.modules.chronicle.load_config", return_value=mock_config):
        chronicle = Chronicle(mock_case_context)

        # Prepare dummy data
        findings = [
            VerificationFinding(
                claim_id="claim_1",
                status=VerificationStatus.SUPPORTED,
                confidence=ConfidenceLevel.HIGH,
                justification=Justification(
                    elements_supported=["fact1"],
                    elements_missing=[],
                    contradictions=[]
                ),
                quotes_with_provenance=["quote1"],
                evidence_refs=["ref1"]
            )
        ]

        citation_findings = [
            CitationFinding(
                citation_text="123 F.2d 456",
                normalized_form="123 F.2d 456",
                status=CitationStatus.VERIFIED,
                confidence=1.0,
                case_details={"name": "Test v. Test", "date": "2023", "court": "Test Court", "url": "http://example.com"},
                reconciliation_notes="notes",
                source_pass="local"
            )
        ]

        gate_result = GateResult(
            document_id="doc_1",
            filing_recommendation=FilingRecommendation.CLEAR,
            risk_score=0.0,
            citation_summary={"total": 1, "verified": 1, "not_found": 0, "unverified": 0, "error": 0},
            claim_summary={"total": 1, "supported": 1, "partially_supported": 0, "not_supported": 0, "contradicted": 0},
            config_snapshot={"engine_version": "3.0", "model": "test_model"},
            timestamp=datetime.now()
        )

        # Call transparency_writer directly
        # This will fail until implemented because the method currently takes only self
        try:
            chronicle.transparency_writer(findings, citation_findings, gate_result)
        except TypeError:
            pytest.fail("transparency_writer does not accept arguments yet")

        report_path = os.path.join(mock_case_context.base_path, "transparency.json")
        assert os.path.exists(report_path)

        with open(report_path, "r") as f:
            data = json.load(f)

        assert data["engine_version"] == "3.0"
        assert data["model"] == "test_model"
        assert data["gate_result"]["risk_score"] == 0.0
        assert len(data["findings"]) == 1
        assert len(data["citation_findings"]) == 1
