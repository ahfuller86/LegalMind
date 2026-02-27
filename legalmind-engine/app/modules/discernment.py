import uuid
import docx
import os
import json
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

    def modality_tagger(self, claim: Claim):
        # Heuristic tagging
        text = claim.text.lower()
        if "witness" in text or "said" in text or "testified" in text:
            claim.expected_modality = "testimony" # Could map to AUDIO_TRANSCRIPT
        elif "video" in text or "footage" in text or "camera" in text:
            claim.expected_modality = "video"
        elif "photo" in text or "image" in text or "picture" in text:
            claim.expected_modality = "image"
