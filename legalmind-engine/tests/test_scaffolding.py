import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "LegalMind Engine v3.0 is running"}

def test_case_init():
    response = client.post("/api/case/init", json={"case_name": "test_case"})
    assert response.status_code == 200
    assert response.json()["status"] == "initialized"

def test_evidence_ingest_start():
    response = client.post("/api/evidence/ingest", json={"file_path": "/tmp/test.pdf"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "dummy_ingest_run_id"
    assert data["status"] == "running"

def test_evidence_ingest_poll():
    response = client.post("/api/evidence/ingest", json={"run_id": "dummy_ingest_run_id"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["items_processed"] == 5

def test_prefile_run():
    response = client.post("/api/prefile/run", json={"brief_path": "/tmp/brief.docx"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "dummy_gate_run_id"
    assert data["status"] == "running"

def test_audit_run():
    response = client.post("/api/audit/run", json={"brief_path": "/tmp/brief.docx"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "dummy_audit_run_id"
    assert data["status"] == "running"

def test_verify_claim():
    response = client.post("/api/verify/claim", json={"claim_id": "claim_123"})
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "verify_job_1"

def test_retrieve_hybrid():
    response = client.post("/api/retrieve/hybrid", json={"claim_id": "claim_123"})
    assert response.status_code == 200
    data = response.json()
    assert data["bundle_id"] == "b1"
    assert data["retrieval_mode"] == "semantic"
