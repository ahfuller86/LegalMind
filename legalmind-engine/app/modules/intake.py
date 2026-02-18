import hashlib
import shutil
import os
import mimetypes
import json
from datetime import datetime
from app.core.stores import CaseContext
from typing import Dict, Any

class Intake:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def file_classifier(self, file_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    def checksum_engine(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def integrity_checker(self, file_path: str) -> bool:
        # Basic check: file exists and is not empty
        if not os.path.exists(file_path):
            return False
        if os.path.getsize(file_path) == 0:
            return False
        return True

    def vault_writer(self, file_path: str) -> str:
        # Returns file_id (hash)
        if not self.integrity_checker(file_path):
            raise ValueError(f"File integrity check failed: {file_path}")

        file_hash = self.checksum_engine(file_path)
        vault_path = os.path.join(self.case_context.vault.vault_path, file_hash)

        # Deduplication: only copy if not exists
        if not os.path.exists(vault_path):
            shutil.copy2(file_path, vault_path)

        # Add to manifest
        self.manifest_builder(file_hash, file_path)

        return file_hash

    def manifest_builder(self, file_id: str, original_path: str):
        manifest_path = os.path.join(self.case_context.base_path, "manifest.json")
        manifest = []
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                try:
                    manifest = json.load(f)
                except json.JSONDecodeError:
                    manifest = []

        # Check if already in manifest
        for entry in manifest:
            if entry["file_id"] == file_id:
                return

        entry = {
            "file_id": file_id,
            "original_name": os.path.basename(original_path),
            "mime_type": self.file_classifier(original_path),
            "upload_timestamp": datetime.now().isoformat(),
            "status": "ingested"
        }
        manifest.append(entry)

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
