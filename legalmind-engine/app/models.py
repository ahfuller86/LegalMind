from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

# --- Enums ---

class Modality(str, Enum):
    PDF_TEXT = "pdf_text"
    PDF_TABLE = "pdf_table"
    OCR_PRINTED = "ocr_printed"
    HANDWRITING_OCR = "handwriting_ocr"
    AUDIO_TRANSCRIPT = "audio_transcript"
    VIDEO_TRANSCRIPT = "video_transcript"
    IMAGE_CAPTION = "image_caption"
    FRAME_OCR = "frame_ocr"

class ClaimType(str, Enum):
    FACTUAL = "factual"
    MEDICAL = "medical"
    DAMAGES = "damages"
    TESTIMONY = "testimony"
    LEGAL_CITATION = "legal_citation"
    PROCEDURAL = "procedural"

class RoutingDecision(str, Enum):
    VERIFY = "verify"
    CITE_CHECK = "cite_check"
    SKIP = "skip"

class RetrievalMode(str, Enum):
    SEMANTIC = "semantic"
    DEGRADED = "degraded"

class VerificationStatus(str, Enum):
    SUPPORTED = "Supported"
    PARTIALLY_SUPPORTED = "Partially Supported"
    NOT_SUPPORTED = "Not Supported"
    CONTRADICTED = "Contradicted"
    NEEDS_MANUAL_REVIEW = "Needs Manual Review"

class CitationStatus(str, Enum):
    VERIFIED = "Verified"
    NOT_FOUND = "Not Found"
    UNVERIFIED = "Unverified"
    AMBIGUOUS = "Ambiguous"
    ERROR = "Error"

class FilingRecommendation(str, Enum):
    CLEAR = "CLEAR"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DO_NOT_FILE = "DO_NOT_FILE"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

# --- Models ---

class EvidenceSegment(BaseModel):
    segment_id: str
    source_asset_id: str
    modality: Modality
    location: str  # Page number, bounding box, timestamp range, or frame number
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    extraction_method: str
    derived: bool
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}

class Chunk(BaseModel):
    chunk_id: str
    segment_ids: List[str]
    source: str
    page_or_timecode: str
    chunk_method: str
    text: str
    context_header: str
    metadata: Dict[str, Any] = {}
    chunk_index: int

class Claim(BaseModel):
    claim_id: str
    text: str
    type: ClaimType
    source_location: str
    priority: int
    expected_modality: Optional[str] = None
    entity_anchors: List[str] = []
    routing: RoutingDecision

class EvidenceBundle(BaseModel):
    bundle_id: str
    claim_id: str
    chunks: List[Chunk]
    retrieval_scores: List[float]
    retrieval_mode: RetrievalMode
    retrieval_warnings: List[str] = []
    modality_filter_applied: bool

class Justification(BaseModel):
    elements_supported: List[str]
    elements_missing: List[str]
    contradictions: List[str]

class VerificationFinding(BaseModel):
    claim_id: str
    status: VerificationStatus
    justification: Justification
    quotes_with_provenance: List[str]  # References only non-derived segments
    evidence_refs: List[str]
    confidence: ConfidenceLevel
    warnings: List[str] = []

class CitationFinding(BaseModel):
    citation_text: str
    normalized_form: str
    status: CitationStatus
    confidence: float
    case_details: Dict[str, str]  # name, date, court, url
    reconciliation_notes: str
    source_pass: str  # local, api, both

class GateResult(BaseModel):
    document_id: str
    filing_recommendation: FilingRecommendation
    risk_score: float
    citation_summary: Dict[str, int]
    claim_summary: Dict[str, int]
    config_snapshot: Dict[str, Any]
    timestamp: datetime

class RunState(BaseModel):
    run_id: str
    status: RunStatus
    progress: float = 0.0
    items_processed: int = 0
    items_total: int = 0
    warnings: List[str] = []
    result_payload: Optional[Dict[str, Any]] = None
    outputs_manifest: Optional[List[str]] = None
