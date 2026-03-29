import os
import pickle
import re
from typing import List, Dict, Any
from eyecite import get_citations, clean_text
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
        # Optimization: Use cached tokenized corpus to avoid reading full JSONL
        corpus_path = os.path.join(self.case_context.index.index_path, "corpus.pkl")
        tokenized_corpus = []
        loaded_from_cache = False

        if os.path.exists(corpus_path):
            try:
                with open(corpus_path, "rb") as f:
                    tokenized_corpus = pickle.load(f)
                loaded_from_cache = True
            except Exception:
                # Corrupted cache, ignore
                tokenized_corpus = []

        # Check for continuity if we loaded from cache and have new chunks
        # chunks are sorted by chunk_index, so check first chunk
        can_append = False
        if loaded_from_cache and chunks:
            # Ensure chunks are sorted (they should be coming from structural_chunker)
            first_chunk_idx = chunks[0].chunk_index
            if len(tokenized_corpus) == first_chunk_idx:
                can_append = True
            else:
                # Discontinuity detected or overlapping, fallback to full rebuild
                pass
        elif loaded_from_cache and not chunks:
            # Just rebuilding index from cache (maybe forced refresh)
            can_append = True

        if can_append and chunks:
            new_tokens = [c.text.split(" ") for c in chunks]
            tokenized_corpus.extend(new_tokens)
            # Update cache
            with open(corpus_path, "wb") as f:
                pickle.dump(tokenized_corpus, f)

        # If we couldn't append or cache was missing/invalid/empty, full rebuild from source
        if not loaded_from_cache or (chunks and not can_append):
            all_chunks = self.case_context.index.get_all_chunks()
            if not all_chunks:
                return
            tokenized_corpus = [c.text.split(" ") for c in all_chunks]
            with open(corpus_path, "wb") as f:
                pickle.dump(tokenized_corpus, f)

        # If corpus is still empty, nothing to index
        if not tokenized_corpus:
            return

        self.bm25_index = BM25Okapi(tokenized_corpus)

        with open(self.bm25_path, "wb") as f:
            pickle.dump(self.bm25_index, f)

    def entity_extractor(self, text: str) -> Dict[str, List[str]]:
        entities = {
            "dates": [],
            "emails": [],
            "urls": [],
            "citations": []
        }

        # Regex for dates
        # Matches YYYY-MM-DD, MM/DD/YYYY, Month DD, YYYY
        date_pattern = r'(?:\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4}\b)'
        entities["dates"] = list(set(re.findall(date_pattern, text)))

        # Regex for emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = list(set(re.findall(email_pattern, text)))

        # Regex for URLs (improved to exclude trailing punctuation)
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?<![.,])'
        entities["urls"] = list(set(re.findall(url_pattern, text)))

        # Citations using eyecite
        try:
            cleaned_text = clean_text(text, ['all_whitespace', 'html'])
            citations = get_citations(cleaned_text)
            entities["citations"] = list(set([c.matched_text() for c in citations]))
        except Exception:
            # Fallback or swallow error to not break pipeline
            pass

        return entities

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
