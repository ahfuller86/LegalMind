import uuid
import asyncio
import os
import tempfile
from app.core.stores import CaseContext
from app.models import RunState, RunStatus
from typing import Dict, Any, Optional
from app.modules.intake import Intake
from app.modules.conversion import Conversion
from app.modules.structuring import Structuring
from app.modules.preservation import Preservation
from app.modules.discernment import Discernment
from app.modules.inquiry import Inquiry
from app.modules.adjudication import Adjudication
from app.modules.chronicle import Chronicle
from app.modules.validation import Validation
from app.modules.sentinel import Sentinel
from app.core.config import load_config

class Dominion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        self.config = load_config()
        self.kpi_stats = {"jobs_run": 0, "errors": 0}

        # Initialize modules
        self.intake = Intake(case_context)
        self.conversion = Conversion(case_context)
        self.structuring = Structuring(case_context)
        self.preservation = Preservation(case_context)
        self.discernment = Discernment(case_context)
        self.inquiry = Inquiry(case_context)
        self.adjudication = Adjudication(case_context)
        self.chronicle = Chronicle(case_context)
        self.validation = Validation(case_context)
        self.sentinel = Sentinel(case_context)

    async def workflow_ingest_case(self, file_path: str) -> RunState:
        run_id = str(uuid.uuid4())

        # Initial state
        run_state = RunState(
            run_id=run_id,
            status=RunStatus.RUNNING,
            progress=0.0
        )
        self.case_context.jobs.save_job(run_state)

        # Launch background task
        asyncio.create_task(self._run_ingest_job(run_id, file_path))

        return run_state

    async def _run_ingest_job(self, run_id: str, file_path: str):
        self.case_context.audit_log.log_event("Dominion", "ingest_job_start", {"run_id": run_id, "file": file_path})

        try:
            # 1. Intake (CPU/IO bound)
            file_hash = await asyncio.to_thread(self.intake.vault_writer, file_path)

            # 2. Conversion (CPU bound)
            segments = []
            mime_type = self.intake.file_classifier(file_path)
            if "pdf" in mime_type:
                segments = await asyncio.to_thread(self.conversion.ingest_pdf_layout, file_path, file_hash)
            elif "word" in mime_type or "docx" in mime_type or "officedocument" in mime_type:
                segments = await asyncio.to_thread(self.conversion.ingest_docx, file_path, file_hash)
            elif "audio" in mime_type:
                segments = await asyncio.to_thread(self.conversion.ingest_audio, file_path, file_hash)
            elif "video" in mime_type:
                segments = await asyncio.to_thread(self.conversion.ingest_video, file_path, file_hash)
            elif "image" in mime_type:
                segments = await asyncio.to_thread(self.conversion.ingest_image, file_path, file_hash)
            else:
                self.case_context.audit_log.log_event("Dominion", "ingest_skip_unsupported", {"mime": mime_type})

            # 3. Structuring (CPU bound)
            chunks = await asyncio.to_thread(self.structuring.structural_chunker, segments)

            # 4. Preservation (IO/CPU bound)
            await asyncio.to_thread(self.preservation.dense_indexer, chunks)
            await asyncio.to_thread(self.preservation.bm25_indexer, chunks)

            self.case_context.audit_log.log_event("Dominion", "ingest_job_complete", {"run_id": run_id})

            # Update job state
            complete_state = RunState(
                run_id=run_id,
                status=RunStatus.COMPLETE,
                progress=1.0,
                items_processed=len(chunks),
                items_total=len(chunks)
            )
            self.case_context.jobs.save_job(complete_state)

        except Exception as e:
            self.case_context.audit_log.log_event("Dominion", "ingest_job_error", {"run_id": run_id, "error": str(e)})
            failed_state = RunState(
                run_id=run_id,
                status=RunStatus.FAILED,
                warnings=[str(e)]
            )
            self.case_context.jobs.save_job(failed_state)

    def get_job_status(self, run_id: str) -> Optional[RunState]:
        return self.case_context.jobs.get_job(run_id)

    async def workflow_audit_brief(self, brief_path: str) -> RunState:
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            status=RunStatus.RUNNING,
            progress=0.0
        )
        self.case_context.jobs.save_job(run_state)
        asyncio.create_task(self._run_audit_job(run_id, brief_path))
        return run_state

    async def _run_audit_job(self, run_id: str, brief_path: str):
        self.kpi_monitor("jobs_run")
        self.case_context.audit_log.log_event("Dominion", "audit_job_start", {"run_id": run_id, "brief": brief_path})

        try:
            # 1. Discernment (CPU bound)
            claims = await asyncio.to_thread(self.discernment.extract_claims, brief_path)

            # 2. Inquiry & Adjudication (Parallel with Semaphore)
            findings = await self._verify_claims_parallel(claims)

            # 3. Chronicle (IO/CPU bound)
            report_path = await asyncio.to_thread(self.chronicle.render_report, findings)

            self.case_context.audit_log.log_event("Dominion", "audit_job_complete", {"run_id": run_id, "findings": len(findings)})

            complete_state = RunState(
                run_id=run_id,
                status=RunStatus.COMPLETE,
                progress=1.0,
                result_payload={"report_path": report_path}
            )
            self.case_context.jobs.save_job(complete_state)

        except Exception as e:
            self.kpi_monitor("errors")
            self.case_context.audit_log.log_event("Dominion", "audit_job_error", {"run_id": run_id, "error": str(e)})
            failed_state = RunState(
                run_id=run_id,
                status=RunStatus.FAILED,
                warnings=[str(e)]
            )
            self.case_context.jobs.save_job(failed_state)

    def kpi_monitor(self, metric: str):
        if metric in self.kpi_stats:
            self.kpi_stats[metric] += 1
        # In production, push to Prometheus/Datadog or write to DB

    async def workflow_cite_check(self, text_or_file: str) -> RunState:
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            status=RunStatus.RUNNING,
            progress=0.0
        )
        self.case_context.jobs.save_job(run_state)
        asyncio.create_task(self._run_cite_check_job(run_id, text_or_file))
        return run_state

    async def _run_cite_check_job(self, run_id: str, text: str):
        self.case_context.audit_log.log_event("Dominion", "cite_check_job_start", {"run_id": run_id})
        try:
            citations = await asyncio.to_thread(self.validation.verify_citations, text)

            # Use Chronicle to render report (even if just citations)
            report_path = await asyncio.to_thread(self.chronicle.render_report, [], citation_findings=citations)

            complete_state = RunState(
                run_id=run_id,
                status=RunStatus.COMPLETE,
                progress=1.0,
                result_payload={"report_path": report_path, "findings_count": len(citations)}
            )
            self.case_context.jobs.save_job(complete_state)
        except Exception as e:
            self.case_context.audit_log.log_event("Dominion", "cite_check_error", {"error": str(e)})
            self.case_context.jobs.save_job(RunState(run_id=run_id, status=RunStatus.FAILED, warnings=[str(e)]))

    def _validate_brief_path(self, brief_path: str) -> None:
        """
        Validates that the brief path is within allowed directories to prevent arbitrary file read.
        Allowed directories: case storage path and system temp directory.
        """
        abs_path = os.path.abspath(brief_path)

        # Allowed prefixes
        allowed_prefixes = [
            os.path.abspath(self.case_context.base_path),
            os.path.abspath(tempfile.gettempdir())
        ]

        is_allowed = False
        for prefix in allowed_prefixes:
            # commonpath ensures that abs_path is under prefix
            try:
                if os.path.commonpath([abs_path, prefix]) == prefix:
                    is_allowed = True
                    break
            except ValueError:
                # paths on different drives
                continue

        if not is_allowed:
            raise ValueError(f"Access denied: Path '{brief_path}' is outside allowed directories.")

        if not os.path.exists(abs_path):
            raise ValueError(f"File not found: {brief_path}")

        if not os.path.isfile(abs_path):
            raise ValueError(f"Path is not a file: {brief_path}")

    async def workflow_prefile_gate(self, brief_path: str) -> RunState:
        run_id = str(uuid.uuid4())
        run_state = RunState(run_id=run_id, status=RunStatus.RUNNING, progress=0.0)
        self.case_context.jobs.save_job(run_state)
        asyncio.create_task(self._run_prefile_gate_job(run_id, brief_path))
        return run_state

    async def _run_prefile_gate_job(self, run_id: str, brief_path: str):
        self.case_context.audit_log.log_event("Dominion", "prefile_gate_start", {"run_id": run_id, "brief": brief_path})
        try:
            # Validate path first
            self._validate_brief_path(brief_path)

            # 1. Read Text (IO bound)
            # Helper to get text for validation
            def read_text():
                import docx
                doc = docx.Document(brief_path)
                return "\n".join([p.text for p in doc.paragraphs])

            full_text = await asyncio.to_thread(read_text)

            # 2. Validation (Parallel) & Audit (Parallel)
            citation_task = asyncio.to_thread(self.validation.verify_citations, full_text)

            async def run_audit_pipeline():
                claims = await asyncio.to_thread(self.discernment.extract_claims, brief_path)
                return await self._verify_claims_parallel(claims)

            citation_findings, claim_findings = await asyncio.gather(citation_task, run_audit_pipeline())

            # 3. Sentinel Gate (CPU bound, lightweight)
            gate_result = await asyncio.to_thread(self.sentinel.gate_evaluator, claim_findings, citation_findings)

            # 4. Chronicle Report (IO bound)
            report_path = await asyncio.to_thread(self.chronicle.render_report, claim_findings, citation_findings, gate_result)

            complete_state = RunState(
                run_id=run_id,
                status=RunStatus.COMPLETE,
                progress=1.0,
                result_payload={"report_path": report_path, "gate_result": gate_result.model_dump()}
            )
            self.case_context.jobs.save_job(complete_state)

        except Exception as e:
            self.case_context.audit_log.log_event("Dominion", "prefile_gate_error", {"error": str(e)})
            self.case_context.jobs.save_job(RunState(run_id=run_id, status=RunStatus.FAILED, warnings=[str(e)]))

    async def _verify_claims_parallel(self, claims):
        findings = []
        sem = asyncio.Semaphore(self.config.MAX_LLM_CONCURRENCY)

        async def verify_single(claim):
            if claim.routing != "verify":
                return None
            async with sem:
                # Retry logic loop
                max_retries = 2
                attempt = 0
                while attempt <= max_retries:
                    try:
                        bundle = await asyncio.to_thread(self.inquiry.retrieve_evidence, claim)
                        finding = await asyncio.to_thread(self.adjudication.verify_claim_skeptical, claim, bundle)
                        return finding
                    except Exception as e:
                        attempt += 1
                        if attempt > max_retries:
                            self.case_context.audit_log.log_event("Dominion", "claim_retry_exhausted", {"claim_id": claim.claim_id})
                            return None
                        await asyncio.sleep(0.5 * attempt)

        tasks = [verify_single(c) for c in claims]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def case_workspace_init(self, case_name: str) -> Dict[str, Any]:
        self.case_context.audit_log.log_event("Dominion", "case_workspace_init_start", {"case_name": case_name})

        # Determine base path for cases
        base_storage = os.path.dirname(self.case_context.base_path)
        if not base_storage or base_storage == ".":
            # Fallback if running from root or unexpected path
            base_storage = "./storage"

        # Initialize new context which creates directories
        new_context = CaseContext(case_name, base_storage_path=base_storage)

        self.case_context.audit_log.log_event("Dominion", "case_workspace_init_complete", {"path": new_context.base_path})
        return {"status": "initialized", "path": new_context.base_path}
