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
from app.modules.validation import Validation
from app.modules.sentinel import Sentinel

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
            citations = self.validation.verify_citations(text)

            # Use Chronicle to render report (even if just citations)
            report_path = self.chronicle.render_report([], citation_findings=citations)

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

    async def workflow_prefile_gate(self, brief_path: str) -> RunState:
        run_id = str(uuid.uuid4())
        run_state = RunState(run_id=run_id, status=RunStatus.RUNNING, progress=0.0)
        self.case_context.jobs.save_job(run_state)
        asyncio.create_task(self._run_prefile_gate_job(run_id, brief_path))
        return run_state

    async def _run_prefile_gate_job(self, run_id: str, brief_path: str):
        self.case_context.audit_log.log_event("Dominion", "prefile_gate_start", {"run_id": run_id, "brief": brief_path})
        try:
            # For simplicity in Phase 2, we read the brief content here or assume Discernment/Validation handles reading
            # In a real app, reading text from docx/pdf should be centralized.
            # Assuming brief_path is readable or we extract text from it.

            # 1. Validation (Parallel)
            # 2. Audit (Parallel)
            # Using asyncio.gather

            # Helper to get text for validation
            # TODO: Add text extraction helper in Dominion or reuse Conversion
            from app.modules.discernment import Discernment # Just to use logic if needed, but extraction is in Discernment
            # We can use Discernment's extract_claims which reads the file, but we need raw text for citations.
            # For now, let's just pass brief_path to validation and let it handle reading (implied) OR extract here.
            # Let's read text simply here for Phase 2:
            import docx
            doc = docx.Document(brief_path)
            full_text = "\n".join([p.text for p in doc.paragraphs])

            citation_task = asyncio.to_thread(self.validation.verify_citations, full_text)

            # Audit task (Discernment -> Inquiry -> Adjudication)
            # We can reuse _run_audit_job logic but we need the return values, not just side effect.
            async def run_audit_pipeline():
                claims = await asyncio.to_thread(self.discernment.extract_claims, brief_path)
                findings = []
                for claim in claims:
                    if claim.routing == "verify":
                        bundle = await asyncio.to_thread(self.inquiry.retrieve_evidence, claim)
                        finding = await asyncio.to_thread(self.adjudication.verify_claim_skeptical, claim, bundle)
                        findings.append(finding)
                return findings

            citation_findings, claim_findings = await asyncio.gather(citation_task, run_audit_pipeline())

            # 3. Sentinel Gate
            gate_result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

            # 4. Chronicle Report
            report_path = self.chronicle.render_report(claim_findings, citation_findings, gate_result)

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
