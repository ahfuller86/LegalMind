import uuid
import docx
import os
import re
import litellm
from typing import List
from app.core.stores import CaseContext
from app.core.config import load_config
from app.models import Claim, ClaimType, RoutingDecision

class Discernment:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def extract_claims(self, file_path: str) -> List[Claim]:
        # Read text first
        try:
            doc = docx.Document(file_path)
            full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            print(f"Error reading doc for claims: {e}")
            return []

        # Try LLM first
        config = load_config()
        if config.CLOUD_MODEL_ALLOWED and os.getenv("OPENAI_API_KEY"):
            return self.llm_decomposer(full_text)

        # Fallback to heuristic
        return self._heuristic_extract(full_text)

    def llm_decomposer(self, text: str) -> List[Claim]:
        try:
            response = litellm.completion(
                model=load_config().LLM_MODEL_NAME,
                messages=[{
                    "role": "system",
                    "content": "Extract factual claims from the legal text. Return a JSON list of objects with 'text', 'type', 'priority' (1-5)."
                }, {
                    "role": "user",
                    "content": text[:10000] # Truncate for safety in this stub
                }],
                max_tokens=2000
            )
            content = response.choices[0].message.content
            # Parse JSON
            import json
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                claims = []
                for item in data:
                    claim = Claim(
                        claim_id=str(uuid.uuid4()),
                        text=item.get("text", ""),
                        type=ClaimType.FACTUAL, # Default or map from item['type']
                        source_location="llm_extracted",
                        priority=item.get("priority", 1),
                        routing=RoutingDecision.VERIFY
                    )
                    self.modality_tagger(claim)
                    claims.append(claim)
                return claims
        except Exception as e:
            print(f"LLM extraction failed: {e}")

        return self._heuristic_extract(text)

    def _heuristic_extract(self, text: str) -> List[Claim]:
        claims = []
        sentences = text.replace("?", ".").replace("!", ".").split(".")
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and not self.boilerplate_filter(sent):
                claim_type = self.claim_classifier(sent)
                claim = Claim(
                    claim_id=str(uuid.uuid4()),
                    text=sent,
                    type=claim_type,
                    source_location="heuristic_body",
                    priority=1,
                    routing=RoutingDecision.VERIFY
                )
                self.modality_tagger(claim)
                claims.append(claim)
        return claims

    def boilerplate_filter(self, text: str) -> bool:
        boilerplate = ["comes now", "respectfully submitted", "wherefore", "judge", "court"]
        return any(b in text.lower() for b in boilerplate)

    # Stubs
    def claim_classifier(self, text: str) -> ClaimType:
        """
        Classifies the claim text into a ClaimType category using heuristics.
        """
        text_lower = text.lower()

        # 1. Legal Citation Check (Regex for common citation patterns)
        # Matches: "123 F.3d 456", "Section 123", "v.", "U.S.C."
        # Note: text is lowercased, so regex must match lowercase
        citation_pattern = r"(\d+\s+u\.?s\.?c\.?)|(section\s+\d+)|(\s+v\.\s+)|(\d+\s+[a-z\.]+\s+\d+)"
        if re.search(citation_pattern, text_lower):
            return ClaimType.LEGAL_CITATION

        # 2. Testimony Check
        testimony_keywords = [
            "testified", "deposed", "stated under oath", "sworn statement",
            "witness said", "witness stated", "according to the witness", "affidavit"
        ]
        if any(kw in text_lower for kw in testimony_keywords):
            return ClaimType.TESTIMONY

        # 3. Damages Check
        damages_keywords = [
            "$", "dollar", "cost", "expense", "compensation", "damages",
            "award", "restitution", "monetary", "financial loss"
        ]
        if any(kw in text_lower for kw in damages_keywords):
            return ClaimType.DAMAGES

        # 4. Medical Check
        medical_keywords = [
            "diagnos", "prognosis", "doctor", "physician", "hospital",
            "surgery", "treatment", "injury", "pain", "symptom", "medical"
        ]
        if any(kw in text_lower for kw in medical_keywords):
            return ClaimType.MEDICAL

        # 5. Procedural Check
        procedural_keywords = [
            "motion", "hearing", "deadline", "filed", "docket",
            "proceeding", "judge", "court order", "service of process"
        ]
        if any(kw in text_lower for kw in procedural_keywords):
            return ClaimType.PROCEDURAL

        # Default to Factual
        return ClaimType.FACTUAL

    def modality_tagger(self, claim: Claim):
        # Heuristic tagging
        text = claim.text.lower()
        if "witness" in text or "said" in text or "testified" in text:
            claim.expected_modality = "testimony" # Could map to AUDIO_TRANSCRIPT
        elif "video" in text or "footage" in text or "camera" in text:
            claim.expected_modality = "video"
        elif "photo" in text or "image" in text or "picture" in text:
            claim.expected_modality = "image"

    def entity_extractor(self, text: str): pass
    def priority_scorer(self, claim: Claim): pass
    def citation_router(self, claim: Claim): pass
