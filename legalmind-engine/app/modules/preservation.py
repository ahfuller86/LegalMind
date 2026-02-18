import os
import pickle
from typing import List, Dict, Any
from app.core.stores import CaseContext
from app.core.config import load_config
from app.models import Chunk
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi

class Preservation:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        self.config = load_config()
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.case_context.index.index_path, "chroma"))

        # Select embedding function based on config
        if self.config.EMBEDDING_PROVIDER == "sentence-transformers":
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        elif self.config.EMBEDDING_PROVIDER == "openai":
             self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"
            )
        else:
            # Fallback or local custom
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

        self.collection = self.chroma_client.get_or_create_collection(
            name=f"case_{self.case_context.case_id}",
            embedding_function=self.embedding_fn
        )
        self.bm25_path = os.path.join(self.case_context.index.index_path, "bm25.pkl")
        self.bm25_index = None
        self._load_bm25()

    def _load_bm25(self):
        if os.path.exists(self.bm25_path):
            with open(self.bm25_path, "rb") as f:
                self.bm25_index = pickle.load(f)

    def dense_indexer(self, chunks: List[Chunk]):
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [f"{c.context_header}\n{c.text}" for c in chunks]
        # Copy metadata to avoid modifying original chunks in place unexpectedly
        metadatas = [c.metadata.copy() for c in chunks]

        # Add source and location to metadata for filtering
        for i, c in enumerate(chunks):
            metadatas[i]["source"] = str(c.source)
            metadatas[i]["page_or_timecode"] = str(c.page_or_timecode)
            metadatas[i]["chunk_index"] = c.chunk_index
            # Ensure modality is string
            if "modality" in metadatas[i]:
                metadatas[i]["modality"] = str(metadatas[i]["modality"])

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    def bm25_indexer(self, chunks: List[Chunk]):
        # Rebuild BM25 for simplicity in Phase 1 (append logic is harder for BM25)
        # Load all chunks to rebuild
        all_chunks = self.case_context.index.get_all_chunks()
        if not all_chunks:
            return

        tokenized_corpus = [c.text.split(" ") for c in all_chunks]
        self.bm25_index = BM25Okapi(tokenized_corpus)

        with open(self.bm25_path, "wb") as f:
            pickle.dump(self.bm25_index, f)

    def entity_extractor(self, text: str):
        pass

    def index_health_reporter(self) -> Dict[str, Any]:
        count = self.collection.count()
        return {
            "status": "healthy" if count > 0 else "empty",
            "stats": {
                "chunk_count": count,
                "bm25_active": self.bm25_index is not None,
                "embedding_provider": self.config.EMBEDDING_PROVIDER
            }
        }
