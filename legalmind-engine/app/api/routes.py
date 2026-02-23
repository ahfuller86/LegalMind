from fastapi import APIRouter, Depends, Query, HTTPException, Body
from typing import Optional, Dict, Any, List
from app.core.stores import CaseContext
from app.modules.dominion import Dominion
from app.models import RunState, RunStatus, EvidenceSegment, Chunk, Claim, EvidenceBundle, VerificationFinding, CitationFinding, GateResult, RetrievalMode

router = APIRouter()

from functools import lru_cache

@lru_cache()
def get_cached_dominion(case_id: str):
    case_context = CaseContext(case_id)
    return Dominion(case_context)

async def get_dominion(case_id: str = Query("default_case")):
    return get_cached_dominion(case_id)

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
async def evidence_register(
    file_path: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    try:
        file_hash = dominion.intake.vault_writer(file_path)
        return {"status": "registered", "file_id": file_hash}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/document/register")
async def document_register(
    file_path: str = Body(..., embed=True),
    case_id: str = Query("default_case")
):
    case_context = CaseContext(case_id)
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
        job = dominion.get_job_status(run_id)
        if job:
            return job
        else:
            raise HTTPException(status_code=404, detail="Job not found")

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required")
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
async def index_health(case_id: str = Query("default_case")):
    case_context = CaseContext(case_id)
    return {"status": "healthy", "degraded": False}

# --- Brief Audit ---

@router.post("/brief/extract-claims", response_model=List[Claim])
async def brief_extract_claims(
    file_path: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    return dominion.discernment.extract_claims(file_path)

@router.post("/audit/run", response_model=RunState)
async def audit_run(
    brief_path: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        job = dominion.get_job_status(run_id)
        if job:
            return job
        else:
            raise HTTPException(status_code=404, detail="Job not found")

    if not brief_path:
        raise HTTPException(status_code=400, detail="brief_path required")
    return await dominion.workflow_audit_brief(brief_path)

@router.post("/retrieve/hybrid", response_model=EvidenceBundle)
async def retrieve_hybrid(
    claim_id: str = Body(..., embed=True),
    text: str = Body(..., embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    # Construct a temporary claim object
    from app.models import Claim, ClaimType, RoutingDecision
    claim = Claim(
        claim_id=claim_id,
        text=text,
        type=ClaimType.FACTUAL,
        source_location="",
        priority=1,
        routing=RoutingDecision.VERIFY
    )
    return dominion.inquiry.retrieve_evidence(claim)

@router.post("/verify/claim", response_model=RunState)
async def verify_claim(
    claim_id: Optional[str] = Body(None, embed=True),
    text: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    # Single claim verification usually is fast enough for sync, but adhering to pattern
    # For now, we'll just run it sync and return COMPLETE
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE)

    # Run sync verification
    # Need to retrieve first
    from app.models import Claim, ClaimType, RoutingDecision
    claim = Claim(
        claim_id=claim_id or "temp",
        text=text or "",
        type=ClaimType.FACTUAL,
        source_location="",
        priority=1,
        routing=RoutingDecision.VERIFY
    )
    bundle = dominion.inquiry.retrieve_evidence(claim)
    finding = dominion.adjudication.verify_claim_skeptical(claim, bundle)

    return RunState(
        run_id="sync_complete",
        status=RunStatus.COMPLETE,
        progress=1.0,
        result_payload=finding.model_dump()
    )

@router.post("/citations/verify-batch", response_model=RunState)
async def citations_verify_batch(
    text: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.COMPLETE)
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    return await dominion.workflow_cite_check(text)

@router.post("/prefile/run", response_model=RunState)
async def prefile_run(
    brief_path: Optional[str] = Body(None, embed=True),
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        return RunState(run_id=run_id, status=RunStatus.RUNNING)
    if not brief_path:
        raise HTTPException(status_code=400, detail="brief_path required")
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

# --- Maintenance ---

@router.post("/maintenance/upgrade-transcripts", response_model=RunState)
async def maintenance_upgrade_transcripts(
    run_id: Optional[str] = Body(None, embed=True),
    dominion: Dominion = Depends(get_dominion)
):
    if run_id:
        job = dominion.get_job_status(run_id)
        if job:
            return job
        else:
            raise HTTPException(status_code=404, detail="Job not found")

    return await dominion.workflow_background_maintenance()
