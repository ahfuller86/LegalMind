import uuid
import os
import pickle
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Any, Dict, Tuple, Optional
from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle, RetrievalMode, Chunk
from app.core.config import load_config

class Inquiry:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        self.config = load_config()
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            client = chromadb.PersistentClient(path=os.path.join(self.case_context.index.index_path, "chroma"))

            if self.config.EMBEDDING_PROVIDER == "sentence-transformers":
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            elif self.config.EMBEDDING_PROVIDER == "openai":
                ef = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model_name="text-embedding-3-small"
                )
            else:
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

            self._collection = client.get_or_create_collection(
                name=f"case_{self.case_context.case_id}",
                embedding_function=ef
            )
        return self._collection

    def retrieve_evidence(self, claim: Claim) -> EvidenceBundle:
        # 1. Dense Retrieval (Chroma)
        dense_results = self._dense_search(claim)

        # 2. Sparse Retrieval (BM25)
        sparse_results = self._bm25_search(claim)

        # 3. RRF Fusion
        merged_chunks, merged_scores = self.rrf_merger(dense_results, sparse_results)

        # 4. Context Expansion (on top 5)
        top_chunks = merged_chunks[:5]
        self.context_expander(top_chunks)

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            claim_id=claim.claim_id,
            chunks=top_chunks,
            retrieval_scores=merged_scores[:5],
            retrieval_mode=RetrievalMode.SEMANTIC, # Actually hybrid
            modality_filter_applied=claim.expected_modality is not None,
            retrieval_warnings=[]
        )

    def _dense_search(self, claim: Claim) -> List[Tuple[Chunk, float]]:
        collection = self._get_collection()

        where_filter = None
        if claim.expected_modality:
            if claim.expected_modality == "video":
                where_filter = {"modality": "video_transcript"}
            elif claim.expected_modality == "testimony":
                where_filter = {"modality": "audio_transcript"}

        results = collection.query(
            query_texts=[claim.text],
            n_results=10,
            where=where_filter
        )

        hits = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                chunk = Chunk(
                    chunk_id=results["ids"][0][i],
                    segment_ids=[],
                    source=str(meta.get("source", "unknown")),
                    page_or_timecode=str(meta.get("page_or_timecode", "unknown")),
                    chunk_method="retrieved_dense",
                    text=doc,
                    context_header="",
                    metadata=meta,
                    chunk_index=int(meta.get("chunk_index", 0))
                )
                score = results["distances"][0][i]
                # Invert distance to similarity for ranking (approx)
                hits.append((chunk, 1.0 / (1.0 + score)))
        return hits

    def _bm25_search(self, claim: Claim) -> List[Tuple[Chunk, float]]:
        bm25_path = os.path.join(self.case_context.index.index_path, "bm25.pkl")
        if not os.path.exists(bm25_path):
            return []

        with open(bm25_path, "rb") as f:
            bm25 = pickle.load(f)

        # Get all chunks to map back index
        all_chunks = self.case_context.index.get_all_chunks()
        if not all_chunks or len(all_chunks) != len(bm25.corpus_size):
            # Index mismatch fallback
            return []

        query_tokens = claim.text.split(" ")
        scores = bm25.get_scores(query_tokens)

        # Get top N indices
        import numpy as np
        top_n = 10
        top_indices = np.argsort(scores)[::-1][:top_n]

        hits = []
        for idx in top_indices:
            score = scores[idx]
            if score > 0:
                chunk = all_chunks[idx]
                # Apply modality filter manually since BM25 library doesn't support metadata filtering natively
                if claim.expected_modality:
                     modality = str(chunk.metadata.get("modality", ""))
                     if claim.expected_modality == "video" and modality != "video_transcript":
                         continue
                     if claim.expected_modality == "testimony" and modality != "audio_transcript":
                         continue

                chunk.chunk_method = "retrieved_bm25"
                hits.append((chunk, float(score)))
        return hits

    def rrf_merger(self, dense_results: List[Tuple[Chunk, float]], sparse_results: List[Tuple[Chunk, float]], k: int = 60) -> Tuple[List[Chunk], List[float]]:
        # RRF logic
        scores = {}
        chunk_map = {}

        for rank, (chunk, _) in enumerate(dense_results):
            chunk_map[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + (1.0 / (k + rank + 1))

        for rank, (chunk, _) in enumerate(sparse_results):
            chunk_map[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + (1.0 / (k + rank + 1))

        # Sort by score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        merged_chunks = [chunk_map[cid] for cid in sorted_ids]
        merged_scores = [scores[cid] for cid in sorted_ids]

        return merged_chunks, merged_scores

    def query_builder(self, claim: Claim): pass
    def modality_filter(self, claim: Claim): pass
    def reranker(self, results: List[Any]): pass

    def context_expander(self, chunks: List[Chunk]):
        """
        Expands the context of retrieved chunks by fetching neighboring chunks
        from the same source based on chunk_index.
        """
        if not chunks:
            return

        collection = self._get_collection()

        for chunk in chunks:
            source = chunk.source
            idx = chunk.chunk_index

            try:
                # Fetch neighbors (previous and next)
                neighbors = collection.get(
                    where={
                        "$and": [
                            {"source": {"$eq": source}},
                            {"chunk_index": {"$in": [idx - 1, idx + 1]}}
                        ]
                    }
                )

                prev_text = ""
                next_text = ""

                if neighbors and neighbors["documents"]:
                    for i, doc in enumerate(neighbors["documents"]):
                        n_meta = neighbors["metadatas"][i]
                        n_idx = n_meta.get("chunk_index")
                        if n_idx == idx - 1:
                            prev_text = doc
                        elif n_idx == idx + 1:
                            next_text = doc

                # Combine text
                expanded_parts = []
                if prev_text:
                    expanded_parts.append(f"[PREVIOUS CONTEXT]\n{prev_text}")

                expanded_parts.append(f"[TARGET CHUNK]\n{chunk.text}")

                if next_text:
                    expanded_parts.append(f"[NEXT CONTEXT]\n{next_text}")

                if prev_text or next_text:
                    chunk.text = "\n\n".join(expanded_parts)
                    if "expansion" not in chunk.metadata:
                         chunk.metadata["expansion"] = {}
                    chunk.metadata["expansion"]["applied"] = True
                    chunk.metadata["expansion"]["neighbor_ids"] = neighbors["ids"] if neighbors else []

            except Exception as e:
                # Log error but continue with other chunks
                self.case_context.audit_log.log_event("Inquiry", "context_expansion_error", {
                    "chunk_id": chunk.chunk_id,
                    "error": str(e)
                })

    def contradiction_hunter(self, claim: Claim): pass
