import uuid
import os
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Any
from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle, RetrievalMode, Chunk

class Inquiry:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def retrieve_evidence(self, claim: Claim) -> EvidenceBundle:
        client = chromadb.PersistentClient(path=os.path.join(self.case_context.index.index_path, "chroma"))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = client.get_or_create_collection(name=f"case_{self.case_context.case_id}", embedding_function=ef)

        results = collection.query(query_texts=[claim.text], n_results=3)

        chunks = []
        scores = []

        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                chunk = Chunk(
                    chunk_id=results["ids"][0][i],
                    segment_ids=[],
                    source=str(meta.get("source", "unknown")),
                    page_or_timecode=str(meta.get("page_or_timecode", "unknown")),
                    chunk_method="retrieved",
                    text=doc,
                    context_header="",
                    metadata=meta,
                    chunk_index=int(meta.get("chunk_index", 0))
                )
                chunks.append(chunk)
                scores.append(results["distances"][0][i])

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            claim_id=claim.claim_id,
            chunks=chunks,
            retrieval_scores=scores,
            retrieval_mode=RetrievalMode.SEMANTIC,
            modality_filter_applied=False,
            retrieval_warnings=[]
        )

    def query_builder(self, claim: Claim): pass
    def modality_filter(self, claim: Claim): pass
    def rrf_merger(self, results: List[Any]): pass
    def reranker(self, results: List[Any]): pass
    def context_expander(self, chunks: List[Any]): pass
    def contradiction_hunter(self, claim: Claim): pass
