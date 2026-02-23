
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import shutil
from fastapi.testclient import TestClient
from fastapi import FastAPI

class TestUpload(unittest.TestCase):
    def setUp(self):
        self.test_dir = "/tmp/legalmind_test_upload"
        os.makedirs(self.test_dir, exist_ok=True)
        self.env_patcher = patch.dict(os.environ, {"LEGALMIND_UPLOAD_DIR": self.test_dir})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_evidence_upload(self):
        mock_dominion = MagicMock()
        mock_stores = MagicMock()

        # We do NOT mock app.models because FastAPI needs real Pydantic models for validation

        with patch.dict(sys.modules, {
            "app.modules.dominion": mock_dominion,
            "app.core.stores": mock_stores,
        }):
            if 'app.api.routes' in sys.modules:
                del sys.modules['app.api.routes']

            from app.api.routes import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            file_content = b"test file content"
            files = {"file": ("test.txt", file_content, "text/plain")}

            response = client.post("/evidence/upload", files=files)

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "uploaded")
            self.assertTrue(data["file_path"].startswith(self.test_dir))
            self.assertTrue(os.path.exists(data["file_path"]))

    def test_evidence_register_async(self):
        mock_dominion = MagicMock()
        mock_stores = MagicMock()

        with patch.dict(sys.modules, {
            "app.modules.dominion": mock_dominion,
            "app.core.stores": mock_stores,
        }):
            if 'app.api.routes' in sys.modules:
                del sys.modules['app.api.routes']

            from app.api.routes import router, get_dominion

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            mock_dom_instance = MagicMock()
            mock_dom_instance.intake.vault_writer.return_value = "hash123"
            app.dependency_overrides[get_dominion] = lambda: mock_dom_instance

            response = client.post("/evidence/register", json={"file_path": "/tmp/anyfile"})

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "registered")
            self.assertEqual(data["file_id"], "hash123")

            mock_dom_instance.intake.vault_writer.assert_called_with("/tmp/anyfile")

if __name__ == '__main__':
    unittest.main()
