import pytest
from app.core.stores import CaseContext
from app.modules.validation import Validation
from app.models import CitationStatus

@pytest.fixture
def validation(tmp_path):
    case_context = CaseContext("test_case_citation", base_storage_path=str(tmp_path))
    return Validation(case_context)

def test_extract_citations(validation):
    text = "See Brown v. Board of Education, 347 U.S. 483 (1954). Also Roe v. Wade, 410 U.S. 113."
    citations = validation.eyecite_extractor(text)
    assert len(citations) >= 2
    # Check that matched text is correct
    texts = [c.matched_text() for c in citations]
    assert "347 U.S. 483" in texts
    assert "410 U.S. 113" in texts

def test_verify_citations_mock(validation):
    text = "Important precedent: 347 U.S. 483."
    findings = validation.verify_citations(text)

    assert len(findings) == 1
    f = findings[0]
    assert f.status == CitationStatus.VERIFIED
    assert f.case_details["name"] == "Brown v. Board of Education"

def test_verify_citations_not_found(validation):
    text = "Made up case: 999 U.S. 999."
    findings = validation.verify_citations(text)

    assert len(findings) == 1
    f = findings[0]
    assert f.status == CitationStatus.NOT_FOUND
