import sys
from unittest.mock import MagicMock

# Mock dependencies BEFORE importing app.api.routes
sys.modules["app.modules.dominion"] = MagicMock()
sys.modules["app.core.stores"] = MagicMock()

# Now import router
from app.api.routes import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import get_dominion
import pytest
import os
import shutil
import asyncio

# Mock app setup
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_evidence_upload():
    # Create a dummy file
    file_content = b"test file content"
    files = {"file": ("test.txt", file_content, "text/plain")}

    response = client.post("/evidence/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "uploaded"
    assert "file_path" in data
    assert os.path.exists(data["file_path"])

    # Clean up
    if os.path.exists(data["file_path"]):
        os.remove(data["file_path"])

@pytest.mark.asyncio
async def test_evidence_register_async():
    # Setup - simulate a file being uploaded
    upload_dir = "/tmp/legalmind_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, "test_async_register.txt")
    with open(file_path, "w") as f:
        f.write("async register test")

    # Mocking
    mock_dominion = MagicMock()
    # vault_writer must be a function/callable for asyncio.to_thread
    mock_dominion.intake.vault_writer = MagicMock(return_value="dummy_hash")

    app.dependency_overrides[get_dominion] = lambda: mock_dominion

    response = client.post("/evidence/register", json={"file_path": file_path})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "registered"
    assert data["file_id"] == "dummy_hash"

    # Verify vault_writer was called
    # Note: asyncio.to_thread runs in a separate thread.
    # client.post waits for the response. By the time it returns, the thread is done.
    mock_dominion.intake.vault_writer.assert_called_with(file_path)

    # Clean up
    if os.path.exists(file_path):
        os.remove(file_path)
