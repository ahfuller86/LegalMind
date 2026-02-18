from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle, VerificationFinding, VerificationStatus, ConfidenceLevel, Justification
from typing import List

class Adjudication:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def verify_claim_skeptical(self, claim: Claim, bundle: EvidenceBundle) -> VerificationFinding:
        status = VerificationStatus.NOT_SUPPORTED
        confidence = ConfidenceLevel.LOW
        quotes = []

        if bundle.chunks:
            # Chroma default is L2. Lower is better.
            best_score = bundle.retrieval_scores[0]
            if best_score < 1.0:
                status = VerificationStatus.SUPPORTED
                confidence = ConfidenceLevel.MEDIUM
                quotes = [bundle.chunks[0].text]
            elif best_score < 1.5:
                status = VerificationStatus.PARTIALLY_SUPPORTED

        return VerificationFinding(
            claim_id=claim.claim_id,
            status=status,
            justification=Justification(
                elements_supported=["Found similar text"] if status == VerificationStatus.SUPPORTED else [],
                elements_missing=[],
                contradictions=[]
            ),
            quotes_with_provenance=quotes,
            evidence_refs=[c.chunk_id for c in bundle.chunks],
            confidence=confidence,
            warnings=[]
        )

    def support_matrix_builder(self): pass
    def quote_only_from_primary(self): pass
    def confidence_calibrator(self): pass
    def confidence_capper(self): pass
    def manual_review_trigger(self): pass
