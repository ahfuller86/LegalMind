from app.core.stores import CaseContext
from app.models import CitationFinding
from typing import List, Any

class Validation:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def eyecite_extractor(self, text: str):
        pass

    def courtlistener_client(self, citation: str):
        pass

    def reconciler(self, local_data: Any, api_data: Any):
        pass

    def deduplicator(self, citations: List[CitationFinding]):
        pass

    def normalizer(self, citation_text: str):
        pass

    def fallback_on_api_down(self):
        pass
