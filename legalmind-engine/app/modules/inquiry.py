from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle
from typing import List

class Inquiry:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def query_builder(self, claim: Claim):
        pass

    def modality_filter(self, claim: Claim):
        pass

    def rrf_merger(self, results: List[Any]):
        pass

    def reranker(self, results: List[Any]):
        pass

    def context_expander(self, chunks: List[Any]):
        pass

    def contradiction_hunter(self, claim: Claim):
        pass
