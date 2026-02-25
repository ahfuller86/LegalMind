import uuid
import docx
import os
import re
import litellm
from typing import List, Dict, Any
from eyecite import get_citations, clean_text
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
                claim = Claim(
                    claim_id=str(uuid.uuid4()),
                    text=sent,
                    type=ClaimType.FACTUAL,
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
    def claim_classifier(self, text: str): pass

    def modality_tagger(self, claim: Claim):
        # Heuristic tagging
        text = claim.text.lower()
        if "witness" in text or "said" in text or "testified" in text:
            claim.expected_modality = "testimony" # Could map to AUDIO_TRANSCRIPT
        elif "video" in text or "footage" in text or "camera" in text:
            claim.expected_modality = "video"
        elif "photo" in text or "image" in text or "picture" in text:
            claim.expected_modality = "image"

    def entity_extractor(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {
                "citations": [],
                "dates": [],
                "emails": [],
                "urls": []
            }

        # 1. Citations using eyecite
        cleaned = clean_text(text, ['all_whitespace', 'html'])
        # Return unique matched text
        citations = list(set([c.matched_text() for c in get_citations(cleaned)]))

        # 2. Dates
        # Patterns:
        # MM/DD/YYYY or MM-DD-YYYY or YYYY-MM-DD
        date_pattern_numeric = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        # YYYY-MM-DD (ISO)
        date_pattern_iso = r'\b\d{4}-\d{2}-\d{2}\b'
        # Month DD, YYYY (e.g., January 1, 2024 or Jan. 1, 2024)
        date_pattern_text = r'\b(?:Jan(?:uary|\.)?|Feb(?:ruary|\.)?|Mar(?:ch|\.)?|Apr(?:il|\.)?|May|Jun(?:e|\.)?|Jul(?:y|\.)?|Aug(?:ust|\.)?|Sep(?:tember|\.|t\.)?|Oct(?:ober|\.)?|Nov(?:ember|\.)?|Dec(?:ember|\.)?)\s+\d{1,2},?\s+\d{4}\b'

        dates = []
        dates.extend(re.findall(date_pattern_numeric, text))
        dates.extend(re.findall(date_pattern_iso, text))
        dates.extend(re.findall(date_pattern_text, text, re.IGNORECASE))
        # Deduplicate
        dates = list(set(dates))

        # 3. Emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = list(set(re.findall(email_pattern, text)))

        # 4. URLs
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w./?%&=]*)?'
        urls = list(set(re.findall(url_pattern, text)))

        return {
            "citations": citations,
            "dates": dates,
            "emails": emails,
            "urls": urls
        }
    def priority_scorer(self, claim: Claim): pass
    def citation_router(self, claim: Claim): pass
