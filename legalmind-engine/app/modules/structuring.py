from app.core.stores import CaseContext
from app.models import Chunk, EvidenceSegment
from typing import List

class Structuring:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def structural_chunker(self, segments: List[EvidenceSegment]):
        pass

    def sentence_chunker(self, text: str):
        pass

    def context_injector(self, chunks: List[Chunk]):
        pass

    def modality_router(self, segments: List[EvidenceSegment]):
        pass

    def chunk_indexer(self, chunks: List[Chunk]):
        pass
