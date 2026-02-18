import uuid
import asyncio
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

class Dominion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        # Initialize modules
        self.intake = Intake(case_context)
        self.conversion = Conversion(case_context)
        self.structuring = Structuring(case_context)
        self.preservation = Preservation(case_context)
        self.discernment = Discernment(case_context)
        self.inquiry = Inquiry(case_context)
        self.adjudication = Adjudication(case_context)
        self.chronicle = Chronicle(case_context)

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
            # 1. Intake
            file_hash = self.intake.vault_writer(file_path)

            # 2. Conversion
            segments = []
            mime_type = self.intake.file_classifier(file_path)
            if "pdf" in mime_type:
                segments = self.conversion.ingest_pdf_layout(file_path, file_hash)
            elif "word" in mime_type or "docx" in mime_type or "officedocument" in mime_type:
                segments = self.conversion.ingest_docx(file_path, file_hash)
            else:
                self.case_context.audit_log.log_event("Dominion", "ingest_skip_unsupported", {"mime": mime_type})

            # 3. Structuring
            chunks = self.structuring.structural_chunker(segments)

            # 4. Preservation
            self.preservation.dense_indexer(chunks)
            self.preservation.bm25_indexer(chunks)

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
        self.case_context.audit_log.log_event("Dominion", "audit_job_start", {"run_id": run_id, "brief": brief_path})

        try:
            # 1. Discernment
            claims = self.discernment.extract_claims(brief_path)

            # 2. Inquiry & Adjudication
            findings = []
            for claim in claims:
                if claim.routing == "verify":
                    bundle = self.inquiry.retrieve_evidence(claim)
                    finding = self.adjudication.verify_claim_skeptical(claim, bundle)
                    findings.append(finding)

            # 3. Chronicle
            report_path = self.chronicle.render_report(findings)

            self.case_context.audit_log.log_event("Dominion", "audit_job_complete", {"run_id": run_id, "findings": len(findings)})

            complete_state = RunState(
                run_id=run_id,
                status=RunStatus.COMPLETE,
                progress=1.0,
                result_payload={"report_path": report_path}
            )
            self.case_context.jobs.save_job(complete_state)

        except Exception as e:
            self.case_context.audit_log.log_event("Dominion", "audit_job_error", {"run_id": run_id, "error": str(e)})
            failed_state = RunState(
                run_id=run_id,
                status=RunStatus.FAILED,
                warnings=[str(e)]
            )
            self.case_context.jobs.save_job(failed_state)

    async def workflow_cite_check(self, text_or_file: str) -> RunState:
        self.case_context.audit_log.log_event("Dominion", "workflow_cite_check", {"input": text_or_file})
        return RunState(
            run_id="dummy_cite_run_id",
            status=RunStatus.RUNNING
        )

    async def workflow_prefile_gate(self, brief_path: str) -> RunState:
        self.case_context.audit_log.log_event("Dominion", "workflow_prefile_gate", {"brief": brief_path})
        return RunState(
            run_id="dummy_gate_run_id",
            status=RunStatus.RUNNING
        )

    async def case_workspace_init(self, case_name: str) -> Dict[str, Any]:
        self.case_context.audit_log.log_event("Dominion", "case_workspace_init_start", {"case_name": case_name})

        # Determine base path for cases
        import os
        base_storage = os.path.dirname(self.case_context.base_path)
        if not base_storage or base_storage == ".":
            # Fallback if running from root or unexpected path
            base_storage = "./storage"

        # Initialize new context which creates directories
        new_context = CaseContext(case_name, base_storage_path=base_storage)

        self.case_context.audit_log.log_event("Dominion", "case_workspace_init_complete", {"path": new_context.base_path})
        return {"status": "initialized", "path": new_context.base_path}
