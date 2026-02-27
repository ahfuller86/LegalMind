import uuid
import os
import pickle
import chromadb
import litellm
from chromadb.utils import embedding_functions
from typing import List, Any, Dict, Tuple
from app.core.stores import CaseContext
from app.models import Claim, EvidenceBundle, RetrievalMode, Chunk
from app.core.config import load_config

class Inquiry:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def retrieve_evidence(self, claim: Claim) -> EvidenceBundle:
        # 1. Dense Retrieval (Chroma)
        dense_results = self._dense_search(claim)

        # 2. Sparse Retrieval (BM25)
        sparse_results = self._bm25_search(claim)

        # 3. RRF Fusion
        merged_chunks, merged_scores = self.rrf_merger(dense_results, sparse_results)

        return EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            claim_id=claim.claim_id,
            chunks=merged_chunks[:5], # Top 5
            retrieval_scores=merged_scores[:5],
            retrieval_mode=RetrievalMode.SEMANTIC, # Actually hybrid
            modality_filter_applied=claim.expected_modality is not None,
            retrieval_warnings=[]
        )

    def _dense_search(self, claim: Claim) -> List[Tuple[Chunk, float]]:
        client = chromadb.PersistentClient(path=os.path.join(self.case_context.index.index_path, "chroma"))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = client.get_or_create_collection(name=f"case_{self.case_context.case_id}", embedding_function=ef)

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
    def context_expander(self, chunks: List[Any]): pass
    def contradiction_hunter(self, claim: Claim) -> List[Chunk]:
        """
        Attempts to find evidence that contradicts the claim.
        Uses an LLM to generate a negated version of the claim if possible,
        otherwise falls back to a simple negation heuristic.
        Then performs a dense search with the negated text.
        """
        config = load_config()
        negated_text = ""
        use_llm = False

        # Determine if we can use LLM
        if config.CLOUD_MODEL_ALLOWED:
            use_llm = True
        elif config.LLM_PROVIDER != "openai":
            # Assume local/private provider is safe/configured
            use_llm = True

        # Check API key if needed (simplistic check)
        if use_llm and config.LLM_PROVIDER == "openai" and not os.getenv("OPENAI_API_KEY"):
            use_llm = False

        if use_llm:
            try:
                prompt = f"Generate a single sentence that directly contradicts the following claim. Do not add any other text.\\nClaim: {claim.text}"
                response = litellm.completion(
                    model=config.LLM_MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    api_base="http://localhost:1234/v1" if config.LLM_PROVIDER == "lmstudio" else None,
                )
                if response.choices and response.choices[0].message:
                    negated_text = response.choices[0].message.content.strip()
            except Exception:
                # Fallback silently on error
                pass

        if not negated_text:
            # Fallback heuristic
            negated_text = f"NOT {claim.text}"

        # Create a temporary claim for search
        negated_claim = claim.model_copy()
        negated_claim.text = negated_text

        # Perform search using the existing dense search method
        # _dense_search returns List[Tuple[Chunk, float]]
        results = self._dense_search(negated_claim)

        chunks = []
        for chunk, score in results:
            # Mark the method so downstream consumers know the origin
            chunk.chunk_method = "contradiction_hunter"
            chunks.append(chunk)

        return chunks
