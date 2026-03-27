import os
import pytest
from unittest.mock import MagicMock
from app.modules.chronicle import Chronicle
from app.core.stores import CaseContext
from app.models import VerificationFinding, CitationFinding, GateResult
from datetime import datetime

@pytest.fixture
def case_context(tmp_path):
    # CaseContext creates directories under base_storage_path/case_id
    # We pass tmp_path as base_storage_path
    return CaseContext("test_case_chronicle", base_storage_path=str(tmp_path))

@pytest.fixture
def chronicle(case_context):
    c = Chronicle(case_context)
    c.pdf_renderer = MagicMock() # Mock out PDF renderer
    return c

def test_timestamp_service(chronicle):
    # Should return a string
    ts = chronicle.timestamp_service()
    assert isinstance(ts, str)
    # Check simple ISO format characteristic
    assert "T" in ts

def test_render_report_no_gate_result(chronicle):
    # Should run without error
    # Pass empty findings
    report_path = chronicle.render_report([], citation_findings=[])
    assert os.path.exists(report_path)

    with open(report_path, "r") as f:
        content = f.read()

    # Check that timestamp IS present in the HTML
    assert "Report Generated:" in content
