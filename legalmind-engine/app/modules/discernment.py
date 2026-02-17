from app.core.stores import CaseContext
from app.models import Claim
from typing import List, Any

class Discernment:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def boilerplate_filter(self, text: str):
        pass

    def llm_decomposer(self, text: str):
        pass

    def claim_classifier(self, text: str):
        pass

    def modality_tagger(self, claim: Claim):
        pass

    def entity_extractor(self, text: str):
        pass

    def priority_scorer(self, claim: Claim):
        pass

    def citation_router(self, claim: Claim):
        pass
