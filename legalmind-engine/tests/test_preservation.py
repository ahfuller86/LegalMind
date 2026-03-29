import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock imports that might be problematic or slow
sys.modules["chromadb"] = MagicMock()
sys.modules["chromadb.utils"] = MagicMock()
sys.modules["rank_bm25"] = MagicMock()

# Now import the class
from app.modules.preservation import Preservation

class TestPreservation:

    @pytest.fixture
    def preservation(self):
        # Patch the __init__ method to avoid initialization logic
        with patch.object(Preservation, '__init__', return_value=None):
            p = Preservation(MagicMock())
            return p

    def test_entity_extractor_dates(self, preservation):
        text = "The contract was signed on 2023-10-27 and expires on Jan 15, 2024."
        entities = preservation.entity_extractor(text)
        assert "2023-10-27" in entities["dates"]
        assert "Jan 15, 2024" in entities["dates"]

    def test_entity_extractor_emails(self, preservation):
        text = "Please contact legal@example.com for assistance."
        entities = preservation.entity_extractor(text)
        assert "legal@example.com" in entities["emails"]

    def test_entity_extractor_urls(self, preservation):
        text = "Visit https://courtlistener.com for more info."
        entities = preservation.entity_extractor(text)
        assert "https://courtlistener.com" in entities["urls"]

    def test_entity_extractor_citations(self, preservation):
        text = "See Brown v. Board of Education, 347 U.S. 483 (1954)."
        entities = preservation.entity_extractor(text)
        assert "347 U.S. 483" in entities["citations"]

    def test_entity_extractor_empty(self, preservation):
        text = ""
        entities = preservation.entity_extractor(text)
        assert entities["dates"] == []
        assert entities["emails"] == []
        assert entities["urls"] == []
        assert entities["citations"] == []
