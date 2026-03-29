import os
import pytest
import shutil
from unittest.mock import MagicMock, patch
from app.core.stores import CaseContext
from app.modules.inquiry import Inquiry
from app.models import Chunk, Claim, ClaimType, RoutingDecision

@pytest.fixture
def case_context(tmp_path):
    case_id = "test_expansion_case"
    return CaseContext(case_id, base_storage_path=str(tmp_path))

@pytest.fixture
def inquiry(case_context):
    return Inquiry(case_context)

def test_context_expander_basic(inquiry, case_context):
    # 1. Setup chunks in Chroma
    # We need to manually add them to the collection that Inquiry will use
    collection = inquiry._get_collection()

    chunks_to_index = [
        Chunk(chunk_id="c0", segment_ids=["s1"], source="doc1", page_or_timecode="1", chunk_method="test", text="Chunk 0", context_header="", chunk_index=0),
        Chunk(chunk_id="c1", segment_ids=["s1"], source="doc1", page_or_timecode="1", chunk_method="test", text="Chunk 1", context_header="", chunk_index=1),
        Chunk(chunk_id="c2", segment_ids=["s1"], source="doc1", page_or_timecode="1", chunk_method="test", text="Chunk 2", context_header="", chunk_index=2),
    ]

    collection.add(
        ids=[c.chunk_id for c in chunks_to_index],
        documents=[c.text for c in chunks_to_index],
        metadatas=[{"source": c.source, "chunk_index": c.chunk_index} for c in chunks_to_index]
    )

    # 2. Test expander on c1
    target_chunk = Chunk(chunk_id="c1", segment_ids=["s1"], source="doc1", page_or_timecode="1", chunk_method="test", text="Chunk 1", context_header="", chunk_index=1)

    inquiry.context_expander([target_chunk])

    assert "[PREVIOUS CONTEXT]\nChunk 0" in target_chunk.text
    assert "[TARGET CHUNK]\nChunk 1" in target_chunk.text
    assert "[NEXT CONTEXT]\nChunk 2" in target_chunk.text
    assert target_chunk.metadata["expansion"]["applied"] is True

def test_context_expander_boundary(inquiry, case_context):
    # 1. Setup chunks in Chroma
    collection = inquiry._get_collection()

    chunks_to_index = [
        Chunk(chunk_id="b0", segment_ids=["s1"], source="doc2", page_or_timecode="1", chunk_method="test", text="Start", context_header="", chunk_index=0),
        Chunk(chunk_id="b1", segment_ids=["s1"], source="doc2", page_or_timecode="1", chunk_method="test", text="Middle", context_header="", chunk_index=1),
    ]

    collection.add(
        ids=[c.chunk_id for c in chunks_to_index],
        documents=[c.text for c in chunks_to_index],
        metadatas=[{"source": c.source, "chunk_index": c.chunk_index} for c in chunks_to_index]
    )

    # 2. Test expander on b0 (no previous)
    chunk0 = Chunk(chunk_id="b0", segment_ids=["s1"], source="doc2", page_or_timecode="1", chunk_method="test", text="Start", context_header="", chunk_index=0)
    inquiry.context_expander([chunk0])

    assert "[PREVIOUS CONTEXT]" not in chunk0.text
    assert "[TARGET CHUNK]\nStart" in chunk0.text
    assert "[NEXT CONTEXT]\nMiddle" in chunk0.text

def test_retrieve_evidence_with_expansion(inquiry, case_context):
    # Setup some chunks
    collection = inquiry._get_collection()
    chunks_to_index = [
        Chunk(chunk_id="x0", segment_ids=["s1"], source="doc3", page_or_timecode="1", chunk_method="test", text="Before", context_header="", chunk_index=0),
        Chunk(chunk_id="x1", segment_ids=["s1"], source="doc3", page_or_timecode="1", chunk_method="test", text="Main evidence", context_header="", chunk_index=1),
        Chunk(chunk_id="x2", segment_ids=["s1"], source="doc3", page_or_timecode="1", chunk_method="test", text="After", context_header="", chunk_index=2),
    ]
    collection.add(
        ids=[c.chunk_id for c in chunks_to_index],
        documents=[c.text for c in chunks_to_index],
        metadatas=[{"source": c.source, "chunk_index": c.chunk_index} for c in chunks_to_index]
    )

    # Mock BM25 to return nothing
    with patch.object(inquiry, "_bm25_search", return_value=[]):
        claim = Claim(claim_id="cl1", text="Main evidence", type=ClaimType.FACTUAL, source_location="doc", priority=1, routing=RoutingDecision.VERIFY)

        bundle = inquiry.retrieve_evidence(claim)

        assert len(bundle.chunks) > 0
        main_chunk = bundle.chunks[0]
        assert "[PREVIOUS CONTEXT]\nBefore" in main_chunk.text
        assert "[TARGET CHUNK]\nMain evidence" in main_chunk.text
        assert "[NEXT CONTEXT]\nAfter" in main_chunk.text
