import uuid
import re
from typing import List
from app.core.stores import CaseContext
from app.models import Chunk, EvidenceSegment

class Structuring:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def structural_chunker(self, segments: List[EvidenceSegment]) -> List[Chunk]:
        chunks = []
        # Get existing chunk count to maintain global index
        existing_chunks = self.case_context.index.get_all_chunks()
        chunk_index = len(existing_chunks)

        for segment in segments:
            # Paragraph splitting
            text = segment.text
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

            for para in paragraphs:
                chunk = Chunk(
                    chunk_id=str(uuid.uuid4()),
                    segment_ids=[segment.segment_id],
                    source=segment.source_asset_id,
                    page_or_timecode=segment.location,
                    chunk_method="paragraph_split",
                    text=para,
                    context_header=f"Source: {segment.source_asset_id} | Location: {segment.location} | Modality: {segment.modality.value}",
                    metadata={
                        "modality": segment.modality,
                        "extraction_method": segment.extraction_method
                    },
                    chunk_index=chunk_index
                )
                chunks.append(chunk)
                chunk_index += 1

        # Persist chunks
        self.case_context.index.add_chunks(chunks)
        return chunks

    def sentence_chunker(self, text: str) -> List[str]:
        # Improved sentence split handling legal abbreviations
        text = text.replace("\n", " ")
        # Protect common abbreviations
        def protect_match(match):
            return match.group(0).replace('.', '<DOT>')

        protected = re.sub(r'(?i)\b(?:v|id|no|see|cf|e\.g|i\.e|u\.s|ref)\.', protect_match, text)
        sentences = re.split(r'(?<=[.!?])\s+', protected)
        sentences = [s.replace('<DOT>', '.') for s in sentences]
        return [s.strip() for s in sentences if s.strip()]

    def context_injector(self, chunks: List[Chunk]):
        # Done in structural_chunker
        pass

    def modality_router(self, segments: List[EvidenceSegment]):
        pass

    def chunk_indexer(self, chunks: List[Chunk]):
        pass
