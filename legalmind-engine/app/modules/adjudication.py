from app.core.stores import CaseContext
from app.core.config import load_config
from app.models import Claim, EvidenceBundle, VerificationFinding, VerificationStatus, ConfidenceLevel, Justification
from typing import List, Optional
import litellm

class Adjudication:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        self.config = load_config()

    def verify_claim_skeptical(self, claim: Claim, bundle: EvidenceBundle) -> VerificationFinding:
        # Heuristic fallback if no LLM allowed or configured
        if not self.config.CLOUD_MODEL_ALLOWED and self.config.LLM_PROVIDER != "lmstudio":
             # Use the distance heuristic from Phase 1/2
             return self._heuristic_verify(claim, bundle)

        # Build prompt
        context = "\n\n".join([c.text for c in bundle.chunks])
        prompt = f"""
        You are a skeptical opposing counsel auditing a legal brief.
        Claim: "{claim.text}"

        Evidence from Record:
        {context}

        Instructions:
        1. Determine if the evidence SUPPORTS, CONTRADICTS, or does NOT SUPPORT the claim.
        2. Be adversarial. Assume the claim is false unless explicitly proven.
        3. If supported, quote the evidence.
        4. Return JSON: {{ "status": "Supported"|"Contradicted"|"Not Supported", "reasoning": "...", "quote": "..." }}
        """

        try:
            # Call LLM via litellm
            # Check if API keys are present or we are in a test env where we should skip
            if not os.getenv("OPENAI_API_KEY") and self.config.LLM_PROVIDER == "openai":
                 return self._heuristic_verify(claim, bundle)

            response = litellm.completion(
                model=self.config.LLM_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                api_base="http://localhost:1234/v1" if self.config.LLM_PROVIDER == "lmstudio" else None,
                max_tokens=500
            )
            content = response.choices[0].message.content

            # Simple parsing of the JSON or text response
            # In a robust implementation, use strict JSON mode or parser
            import json
            import re

            # Try to find JSON blob
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                status_str = data.get("status", "Needs Manual Review")
                # Map string to Enum
                try:
                    status = VerificationStatus(status_str)
                except:
                    status = VerificationStatus.NEEDS_MANUAL_REVIEW

                return VerificationFinding(
                    claim_id=claim.claim_id,
                    status=status,
                    justification=Justification(
                        elements_supported=[data.get("reasoning", "")],
                        elements_missing=[],
                        contradictions=[]
                    ),
                    quotes_with_provenance=[data.get("quote", "")] if data.get("quote") else [],
                    evidence_refs=[c.chunk_id for c in bundle.chunks],
                    confidence=ConfidenceLevel.HIGH,
                    warnings=[]
                )

            # Fallback if no JSON found
            return self._heuristic_verify(claim, bundle)

        except Exception as e:
            print(f"LLM Verification failed: {e}")
            return self._heuristic_verify(claim, bundle)

    def _heuristic_verify(self, claim: Claim, bundle: EvidenceBundle) -> VerificationFinding:
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
            warnings=["Heuristic verification used"]
        )

    def support_matrix_builder(self): pass
    def quote_only_from_primary(self): pass
    def confidence_calibrator(self): pass
    def confidence_capper(self): pass
    def manual_review_trigger(self): pass
