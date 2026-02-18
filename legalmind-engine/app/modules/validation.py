from app.core.stores import CaseContext
from app.models import CitationFinding, CitationStatus, ConfidenceLevel
from typing import List, Any, Dict, Optional
from eyecite import get_citations, clean_text

class Validation:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def eyecite_extractor(self, text: str) -> List[Any]:
        # Clean text
        cleaned_text = clean_text(text, ['all_whitespace', 'html'])
        citations = get_citations(cleaned_text)
        return citations

    def courtlistener_client(self, citation_str: str) -> Dict[str, Any]:
        # Stub implementation to avoid external network dependency in tests
        # This will be replaced by actual API call in Phase 2+
        if "347 U.S. 483" in citation_str: # Brown v. Board
             return {
                 "status": "found",
                 "title": "Brown v. Board of Education",
                 "date_filed": "1954-05-17",
                 "court": "scotus"
             }
        return {"status": "not_found"}

    def reconciler(self, api_data: Dict[str, Any]) -> CitationStatus:
        if api_data.get("status") == "found":
            return CitationStatus.VERIFIED
        return CitationStatus.NOT_FOUND

    def normalizer(self, citation_text: str) -> str:
        return citation_text.lower().replace(".", "").replace(" ", "")

    def deduplicator(self, findings: List[CitationFinding]) -> List[CitationFinding]:
        seen = set()
        unique = []
        for f in findings:
            if f.normalized_form not in seen:
                seen.add(f.normalized_form)
                unique.append(f)
        return unique

    def verify_citations(self, text: str) -> List[CitationFinding]:
        citations = self.eyecite_extractor(text)

        findings = []
        for citation in citations:
            cit_str = citation.matched_text()

            # API check (Mocked)
            api_res = self.courtlistener_client(cit_str)
            status = self.reconciler(api_res)

            # Use explicit confidence level enum if defined in models, else float 1.0/0.0
            confidence = 1.0 if status == CitationStatus.VERIFIED else 0.0

            finding = CitationFinding(
                citation_text=cit_str,
                normalized_form=self.normalizer(cit_str),
                status=status,
                confidence=confidence,
                case_details={
                    "name": api_res.get("title", "Unknown"),
                    "date": api_res.get("date_filed", ""),
                    "court": api_res.get("court", ""),
                    "url": ""
                },
                reconciliation_notes="Mock verification",
                source_pass="both"
            )
            findings.append(finding)

        return self.deduplicator(findings)
