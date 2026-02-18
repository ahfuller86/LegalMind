import os
import json
import shutil
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models import EvidenceSegment, Chunk, RunState, RunStatus

class JobStore:
    def __init__(self, case_id: str, base_path: str):
        self.case_id = case_id
        self.base_path = base_path
        self.jobs_path = os.path.join(base_path, "jobs")
        os.makedirs(self.jobs_path, exist_ok=True)

    def save_job(self, run_state: RunState):
        file_path = os.path.join(self.jobs_path, f"{run_state.run_id}.json")
        with open(file_path, "w") as f:
            f.write(run_state.model_dump_json())

    def get_job(self, run_id: str) -> Optional[RunState]:
        file_path = os.path.join(self.jobs_path, f"{run_id}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            try:
                return RunState(**json.load(f))
            except json.JSONDecodeError:
                return None

class EvidenceVault:
    def __init__(self, case_id: str, base_path: str):
        self.case_id = case_id
        self.base_path = base_path
        self.vault_path = os.path.join(base_path, "vault")
        os.makedirs(self.vault_path, exist_ok=True)

    def store_file(self, filename: str, content: bytes, metadata: Dict[str, Any]) -> str:
        sha256_hash = hashlib.sha256(content).hexdigest()
        file_path = os.path.join(self.vault_path, sha256_hash)

        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.write(content)

        return sha256_hash

    def store_file_from_path(self, source_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(source_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()

        target_path = os.path.join(self.vault_path, file_hash)
        if not os.path.exists(target_path):
            shutil.copy2(source_path, target_path)

        return file_hash

    def get_file(self, file_id: str) -> bytes:
        file_path = os.path.join(self.vault_path, file_id)
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        return b""

class EvidenceLedger:
    def __init__(self, case_id: str, base_path: str):
        self.case_id = case_id
        self.base_path = base_path
        self.ledger_path = os.path.join(base_path, "ledger")
        os.makedirs(self.ledger_path, exist_ok=True)
        self.segments_file = os.path.join(self.ledger_path, "segments.jsonl")

    def append_segment(self, segment: EvidenceSegment):
        with open(self.segments_file, "a") as f:
            f.write(segment.model_dump_json() + "\n")

    def get_segments(self, source_asset_id: str) -> List[EvidenceSegment]:
        segments = []
        if not os.path.exists(self.segments_file):
            return segments

        with open(self.segments_file, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("source_asset_id") == source_asset_id:
                        segments.append(EvidenceSegment(**data))
                except json.JSONDecodeError:
                    continue
        return segments

    def update_segment(self, updated_segment: EvidenceSegment):
        """
        Updates an existing segment by rewriting the JSONL file.
        Note: This is not concurrency-safe for high-volume parallel writes.
        Intended for maintenance tasks.
        """
        all_segments = self.get_all_segments()
        found = False
        new_segments = []

        for seg in all_segments:
            if seg.segment_id == updated_segment.segment_id:
                new_segments.append(updated_segment)
                found = True
            else:
                new_segments.append(seg)

        if found:
            # Atomic write pattern: write to temp, then rename
            temp_file = self.segments_file + ".tmp"
            with open(temp_file, "w") as f:
                for seg in new_segments:
                    f.write(seg.model_dump_json() + "\n")
            os.replace(temp_file, self.segments_file)

    def get_all_segments(self) -> List[EvidenceSegment]:
        segments = []
        if not os.path.exists(self.segments_file):
            return segments

        with open(self.segments_file, "r") as f:
            for line in f:
                try:
                    segments.append(EvidenceSegment(**json.loads(line)))
                except json.JSONDecodeError:
                    continue
        return segments

class RetrievalIndex:
    def __init__(self, case_id: str, base_path: str):
        self.case_id = case_id
        self.base_path = base_path
        self.index_path = os.path.join(base_path, "index")
        os.makedirs(self.index_path, exist_ok=True)
        self.chunks_file = os.path.join(self.index_path, "chunks.jsonl")

    def add_chunks(self, chunks: List[Chunk]):
        with open(self.chunks_file, "a") as f:
            for chunk in chunks:
                f.write(chunk.model_dump_json() + "\n")

    def get_all_chunks(self) -> List[Chunk]:
        chunks = []
        if not os.path.exists(self.chunks_file):
            return chunks

        with open(self.chunks_file, "r") as f:
            for line in f:
                try:
                    chunks.append(Chunk(**json.loads(line)))
                except json.JSONDecodeError:
                    continue
        return chunks

    def query(self, query_text: str, filters: Dict[str, Any] = None) -> List[Chunk]:
        # This will be implemented by Preservation/Inquiry using Chroma/BM25
        # RetrievalIndex acts as the store, but query might be delegated
        return []

class AuditLog:
    def __init__(self, case_id: str, base_path: str):
        self.case_id = case_id
        self.base_path = base_path
        self.log_path = os.path.join(base_path, "audit_log")
        os.makedirs(self.log_path, exist_ok=True)
        self.log_file = os.path.join(self.log_path, "audit.jsonl")

    def log_event(self, module: str, action: str, details: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "case_id": self.case_id,
            "module": module,
            "action": action,
            "details": details
        }
        # Print for debug
        print(f"AUDIT: {json.dumps(entry)}")

        # Persist
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

class CaseContext:
    def __init__(self, case_id: str, base_storage_path: str = "./storage"):
        self.case_id = case_id
        self.base_path = os.path.join(base_storage_path, case_id)
        self.vault = EvidenceVault(case_id, self.base_path)
        self.ledger = EvidenceLedger(case_id, self.base_path)
        self.index = RetrievalIndex(case_id, self.base_path)
        self.audit_log = AuditLog(case_id, self.base_path)
        self.jobs = JobStore(case_id, self.base_path)
