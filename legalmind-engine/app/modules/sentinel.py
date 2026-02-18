import asyncio
from typing import Dict, Any, List
from datetime import datetime
from app.core.stores import CaseContext
from app.models import GateResult, FilingRecommendation, VerificationFinding, CitationFinding, VerificationStatus, CitationStatus

class Sentinel:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def gate_evaluator(self, claim_findings: List[VerificationFinding], citation_findings: List[CitationFinding]) -> GateResult:
        # Calculate risk first to use it in recommendation
        risk_score = self.risk_scorer(claim_findings, citation_findings)

        # Determine recommendation
        recommendation = FilingRecommendation.CLEAR

        # Hard stop if ANY citation is not found
        if any(c.status == CitationStatus.NOT_FOUND for c in citation_findings):
            recommendation = FilingRecommendation.DO_NOT_FILE
        # Review required if ANY claim is contradicted
        elif any(f.status == VerificationStatus.CONTRADICTED for f in claim_findings):
            recommendation = FilingRecommendation.REVIEW_REQUIRED
        # Review required if risk score is high
        elif risk_score > 15.0:
            recommendation = FilingRecommendation.REVIEW_REQUIRED

        citation_summary = {
            "total": len(citation_findings),
            "verified": sum(1 for c in citation_findings if c.status == CitationStatus.VERIFIED),
            "not_found": sum(1 for c in citation_findings if c.status == CitationStatus.NOT_FOUND),
            "unverified": sum(1 for c in citation_findings if c.status == CitationStatus.UNVERIFIED),
            "error": sum(1 for c in citation_findings if c.status == CitationStatus.ERROR)
        }

        claim_summary = {
            "total": len(claim_findings),
            "supported": sum(1 for f in claim_findings if f.status == VerificationStatus.SUPPORTED),
            "partially_supported": sum(1 for f in claim_findings if f.status == VerificationStatus.PARTIALLY_SUPPORTED),
            "not_supported": sum(1 for f in claim_findings if f.status == VerificationStatus.NOT_SUPPORTED),
            "contradicted": sum(1 for f in claim_findings if f.status == VerificationStatus.CONTRADICTED)
        }

        return GateResult(
            document_id="doc_1", # Placeholder for document ID being audited
            filing_recommendation=recommendation,
            risk_score=risk_score,
            citation_summary=citation_summary,
            claim_summary=claim_summary,
            config_snapshot=self.config_snapshot(),
            timestamp=datetime.now()
        )

    def risk_scorer(self, claim_findings: List[VerificationFinding], citation_findings: List[CitationFinding]) -> float:
        score = 0.0

        # Claims
        for f in claim_findings:
            if f.status == VerificationStatus.CONTRADICTED:
                score += 10.0
            elif f.status == VerificationStatus.NOT_SUPPORTED:
                score += 5.0
            elif f.status == VerificationStatus.PARTIALLY_SUPPORTED:
                score += 2.0

        # Citations
        for c in citation_findings:
            if c.status == CitationStatus.NOT_FOUND:
                score += 20.0 # High risk for fake/wrong citations
            elif c.status == CitationStatus.UNVERIFIED:
                score += 5.0
            elif c.status == CitationStatus.ERROR:
                score += 5.0

        return min(score, 100.0)

    def config_snapshot(self) -> Dict[str, Any]:
        return {
            "engine_version": "3.0",
            "model": "stub-model", # Replace with actual config
            "retrieval_mode": "hybrid",
            "privacy_mode": "local-only"
        }

    def escalation_emitter(self):
        pass
