import os
import shutil
import time
import json
import pytest
import sys

# Ensure app is in path
sys.path.append(os.path.join(os.getcwd(), "legalmind-engine"))

from app.core.stores import AuditLog

@pytest.fixture
def clean_audit_log():
    case_id = "test_case_audit"
    base_path = "./test_storage_audit"
    if os.path.exists(base_path):
        shutil.rmtree(base_path)
    yield case_id, base_path
    if os.path.exists(base_path):
        shutil.rmtree(base_path)

def test_audit_log_async_write(clean_audit_log):
    case_id, base_path = clean_audit_log
    audit_log = AuditLog(case_id, base_path)

    # Log an event
    details = {"foo": "bar"}
    audit_log.log_event("TestModule", "TestAction", details)

    # Since it's async, we wait a bit or use queue join
    # Accessing private _queue to wait
    # We must ensure the worker has picked it up.
    # queue.join() blocks until all items in the queue have been gotten and processed.
    AuditLog._queue.join()

    # Verify file content
    log_file = os.path.join(base_path, "audit_log", "audit.jsonl")
    assert os.path.exists(log_file)

    with open(log_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["case_id"] == case_id
        assert entry["module"] == "TestModule"
        assert entry["action"] == "TestAction"
        assert entry["details"] == details
        assert "timestamp" in entry

def test_audit_log_multiple_writes(clean_audit_log):
    case_id, base_path = clean_audit_log
    audit_log = AuditLog(case_id, base_path)

    count = 100
    for i in range(count):
        audit_log.log_event("TestModule", "TestAction", {"i": i})

    AuditLog._queue.join()

    log_file = os.path.join(base_path, "audit_log", "audit.jsonl")
    with open(log_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == count
