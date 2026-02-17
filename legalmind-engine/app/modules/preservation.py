from app.core.stores import CaseContext
from app.models import Chunk
from typing import List, Dict, Any

class Preservation:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def dense_indexer(self, chunks: List[Chunk]):
        pass

    def bm25_indexer(self, chunks: List[Chunk]):
        pass

    def entity_extractor(self, text: str):
        pass

    def index_health_reporter(self) -> Dict[str, Any]:
        return {"status": "ok", "stats": {}}
