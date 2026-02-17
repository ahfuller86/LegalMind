from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle, VerificationFinding
from typing import List

class Adjudication:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def verify_claim_skeptical(self, claim: Claim, bundle: EvidenceBundle) -> VerificationFinding:
        pass

    def support_matrix_builder(self):
        pass

    def quote_only_from_primary(self):
        pass

    def confidence_calibrator(self):
        pass

    def confidence_capper(self):
        pass

    def manual_review_trigger(self):
        pass
