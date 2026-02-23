import hashlib
import shutil
import os
import mimetypes
import json
import fcntl
import contextlib
from datetime import datetime
from app.core.stores import CaseContext
from app.core.config import load_config
from typing import Dict, Any

@contextlib.contextmanager
def file_lock(lock_path: str):
    with open(lock_path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

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
        if not self._validate_path(file_path):
            raise ValueError(f"Access denied: Path {file_path} is outside allowed directories.")

        if not self.integrity_checker(file_path):
            raise ValueError(f"File integrity check failed: {file_path}")

        # Delegate hashing and storage to Vault
        file_hash = self.case_context.vault.store_file_from_path(file_path)

        # Add to manifest
        self.manifest_builder(file_hash, file_path)

        return file_hash

    def _validate_path(self, file_path: str) -> bool:
        # Prevent path traversal and restrict to /tmp or explicitly allowed directories
        abs_path = os.path.abspath(file_path)
        config = load_config()

        # Resolve allowed paths
        allowed_prefixes = []
        # Explicitly allow upload directory
        allowed_prefixes.append(os.path.abspath(config.UPLOAD_DIR))

        for p in config.ALLOWED_INPUT_PATHS:
            if p == ".":
                allowed_prefixes.append(os.getcwd())
            else:
                allowed_prefixes.append(os.path.abspath(p))

        is_allowed = any(abs_path.startswith(prefix) for prefix in allowed_prefixes)

        if not is_allowed:
            return False

        # Basic path traversal check (though startswith helps)
        if ".." in file_path and not is_allowed:
             # Double check if absolute path is still safe
             pass

        return os.path.isfile(abs_path)

    def manifest_builder(self, file_id: str, original_path: str):
        manifest_path = os.path.join(self.case_context.base_path, "manifest.json")
        lock_path = manifest_path + ".lock"

        with file_lock(lock_path):
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
