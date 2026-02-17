from fastapi import APIRouter, Depends, Query, HTTPException, Body
from typing import Optional, Dict, Any, List
from app.core.stores import CaseContext
from app.modules.dominion import Dominion
from app.models import RunState, RunStatus, EvidenceSegment, Chunk, Claim, EvidenceBundle, VerificationFinding, CitationFinding, GateResult, RetrievalMode

router = APIRouter()

async def get_case_context(case_id: str = Query("default_case")):
    return CaseContext(case_id)

async def get_dominion(case_context: CaseContext = Depends(get_case_context)):
    return Dominion(case_context)

# --- Case & Evidence ---

@router.post("/case/init")
async def case_init(
    case_name: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    return await dominion.case_workspace_init(case_name)

@router.get("/case/status")
async def case_status(case_id: str):
    # Stub
    return {"status": "ok", "manifest": [], "index_health": {}}

@router.post("/evidence/register")
async def evidence_register(file_path: str = Body(..., embed=True), case_context: CaseContext = Depends(get_case_context)):
    # Stub
    return {"status": "registered", "file_id": "dummy_hash"}

@router.post("/document/register")
async def document_register(file_path: str = Body(..., embed=True), case_context: CaseContext = Depends(get_case_context)):
    # Stub
    return {"status": "registered", "document_id": "dummy_doc_id"}

# --- Pipeline Operations (Start/Poll) ---

@router.post("/evidence/ingest", response_model=RunState)
async def evidence_ingest(
    file_path: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.RUNNING, items_processed=5, items_total=10)
    return await dominion.workflow_ingest_case(file_path)

@router.post("/index/chunk", response_model=RunState)
async def index_chunk(
    segment_ids: Optional[List[str]] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.RUNNING)
    return RunState(run_id="chunk_job_1", status=RunStatus.RUNNING)

@router.post("/index/build", response_model=RunState)
async def index_build(
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE)
    return RunState(run_id="index_job_1", status=RunStatus.RUNNING)

@router.get("/index/health")
async def index_health(case_context: CaseContext = Depends(get_case_context)):
    return {"status": "healthy", "degraded": False}

# --- Brief Audit ---

@router.post("/brief/extract-claims", response_model=List[Claim])
async def brief_extract_claims(
    file_path: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    return []

@router.post("/audit/run", response_model=RunState)
async def audit_run(
    brief_path: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.RUNNING)
    return await dominion.workflow_audit_brief(brief_path)

@router.post("/retrieve/hybrid", response_model=EvidenceBundle)
async def retrieve_hybrid(
    claim_id: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    # Return dummy bundle
    return EvidenceBundle(
        bundle_id="b1", claim_id=claim_id, chunks=[], retrieval_scores=[],
        retrieval_mode=RetrievalMode.SEMANTIC, modality_filter_applied=False
    )

@router.post("/verify/claim", response_model=RunState)
async def verify_claim(
    claim_id: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE)
    return RunState(run_id="verify_job_1", status=RunStatus.RUNNING)

@router.post("/citations/verify-batch", response_model=RunState)
async def citations_verify_batch(
    text: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE)
    return await dominion.workflow_cite_check(text)

@router.post("/prefile/run", response_model=RunState)
async def prefile_run(
    brief_path: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.RUNNING)
    return await dominion.workflow_prefile_gate(brief_path)

@router.post("/report/render", response_model=RunState)
async def report_render(
    findings_ids: Optional[List[str]] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE, result_payload={"path": "/tmp/report.html"})
    return RunState(run_id="report_job_1", status=RunStatus.RUNNING)
