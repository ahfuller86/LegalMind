import uuid
import docx
from typing import List
from app.core.stores import CaseContext
from app.models import Claim, ClaimType, RoutingDecision

class Discernment:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def extract_claims(self, file_path: str) -> List[Claim]:
        # Basic heuristic extraction
        claims = []
        try:
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Split sentences (using Structuring logic or simple split)
                sentences = text.replace("?", ".").replace("!", ".").split(".")

                for sent in sentences:
                    sent = sent.strip()
                    if len(sent) > 20 and not self.boilerplate_filter(sent):
                        claim = Claim(
                            claim_id=str(uuid.uuid4()),
                            text=sent,
                            type=ClaimType.FACTUAL,
                            source_location="doc_body",
                            priority=1,
                            expected_modality=None,
                            entity_anchors=[],
                            routing=RoutingDecision.VERIFY
                        )
                        claims.append(claim)

        except Exception as e:
            print(f"Error extracting claims from {file_path}: {e}")

        return claims

    def boilerplate_filter(self, text: str) -> bool:
        boilerplate = ["comes now", "respectfully submitted", "wherefore", "judge", "court"]
        return any(b in text.lower() for b in boilerplate)

    # Stubs
    def llm_decomposer(self, text: str): pass
    def claim_classifier(self, text: str): pass
    def modality_tagger(self, claim: Claim): pass
    def entity_extractor(self, text: str): pass
    def priority_scorer(self, claim: Claim): pass
    def citation_router(self, claim: Claim): pass
