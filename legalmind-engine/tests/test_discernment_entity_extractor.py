import pytest
from app.core.stores import CaseContext
from app.modules.discernment import Discernment

@pytest.fixture
def discernment(tmp_path):
    case_context = CaseContext("test_case_discernment", base_storage_path=str(tmp_path))
    return Discernment(case_context)

def test_entity_extractor_empty(discernment):
    text = ""
    entities = discernment.entity_extractor(text)
    assert entities == {
        "citations": [],
        "dates": [],
        "emails": [],
        "urls": []
    }

def test_entity_extractor_dates(discernment):
    text = "The event happened on 12/25/2023. Also on January 1, 2024 and 2023-05-05."
    entities = discernment.entity_extractor(text)
    assert "12/25/2023" in entities["dates"]
    assert "January 1, 2024" in entities["dates"]
    assert "2023-05-05" in entities["dates"]

def test_entity_extractor_emails(discernment):
    text = "Contact us at support@legalmind.com or admin@example.org."
    entities = discernment.entity_extractor(text)
    assert "support@legalmind.com" in entities["emails"]
    assert "admin@example.org" in entities["emails"]

def test_entity_extractor_urls(discernment):
    text = "Visit https://www.legalmind.tech/ for more info."
    entities = discernment.entity_extractor(text)
    # Note: URL regex might catch trailing slash or not, depending on implementation
    # I'll assert partial match if needed, but exact is better
    urls = entities["urls"]
    assert "https://www.legalmind.tech/" in urls or "https://www.legalmind.tech" in urls

def test_entity_extractor_citations(discernment):
    text = "As stated in Brown v. Board of Education, 347 U.S. 483 (1954)."
    entities = discernment.entity_extractor(text)
    # Assuming implementation returns the citation string or matched text
    citations = entities["citations"]
    assert any("347 U.S. 483" in c for c in citations)

def test_entity_extractor_mixed(discernment):
    text = "Email me at user@test.com about 347 U.S. 483 on 05/05/2020."
    entities = discernment.entity_extractor(text)
    assert "user@test.com" in entities["emails"]
    assert any("347 U.S. 483" in c for c in entities["citations"])
    assert "05/05/2020" in entities["dates"]
