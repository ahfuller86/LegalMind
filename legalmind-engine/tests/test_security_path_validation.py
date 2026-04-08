import sys
import os
import pytest
import tempfile
import uuid
from unittest.mock import MagicMock, patch

# Specific mocks for things that are used as base classes
class MockBaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def model_dump_json(self):
        import json
        return json.dumps(self.__dict__, default=str)
    def model_dump(self):
        return self.__dict__

@pytest.fixture
def dominion(tmp_path):
    """
    Fixture that sets up Dominion with mocked dependencies.
    It uses patch.dict to modify sys.modules only for the duration of the test,
    preventing side effects on other tests.
    """
    mock_dict = {}

    # 1. Mock external heavy libraries
    mock_libs = [
        "pydantic", "pydantic_settings", "fastapi", "uvicorn",
        "requests", "python-docx", "docx", "httpx", "jinja2",
        "python_multipart", "pdfplumber", "pypdf",
        "sentence_transformers", "chromadb", "rank_bm25",
        "litellm", "annotated_types", "reportlab", "eyecite",
        "weasyprint", "openai_whisper", "ffmpeg_python",
        "pytesseract", "PIL", "pdf2image"
    ]

    for lib in mock_libs:
        mock_dict[lib] = MagicMock()

    # 2. Setup Pydantic mock specifically
    mock_pydantic = MagicMock()
    mock_pydantic.BaseModel = MockBaseModel
    mock_dict["pydantic"] = mock_pydantic

    # 3. Mock internal app modules that invoke heavy libs
    app_modules_to_mock = [
        "app.modules.intake",
        "app.modules.conversion",
        "app.modules.structuring",
        "app.modules.preservation",
        "app.modules.discernment",
        "app.modules.inquiry",
        "app.modules.adjudication",
        "app.modules.chronicle",
        "app.modules.validation",
        "app.modules.sentinel",
        "app.core.config"
    ]

    for mod in app_modules_to_mock:
        mock_dict[mod] = MagicMock()

    # 4. Setup specific return values
    mock_dict["app.core.config"].load_config.return_value = MagicMock()

    # 5. Apply the patch
    with patch.dict(sys.modules, mock_dict):
        # 6. Clean state: Ensure target modules are re-imported with mocks
        # We must remove them if they are already cached from real environment or previous tests
        target_modules = ["app.modules.dominion", "app.core.stores", "app.models"]
        for mod in target_modules:
            if mod in sys.modules:
                del sys.modules[mod]

        # 7. Import strictly inside the patched environment
        from app.core.stores import CaseContext
        from app.modules.dominion import Dominion

        # 8. Initialize
        case_context = CaseContext(f"test_case_{uuid.uuid4()}", base_storage_path=str(tmp_path))
        # Dominion init will trigger imports of Intake, Conversion etc. which are now mocked
        dom = Dominion(case_context)

        yield dom

# Tests
def test_validate_brief_path_valid_case_storage(dominion, tmp_path):
    """Test that a file inside the case storage directory is allowed."""
    case_dir = dominion.case_context.base_path
    os.makedirs(case_dir, exist_ok=True)

    valid_file = os.path.join(case_dir, "valid_brief.docx")
    with open(valid_file, "w") as f:
        f.write("content")

    dominion._validate_brief_path(valid_file)

def test_validate_brief_path_valid_temp_dir(dominion, tmp_path):
    """Test that a file inside the system temp directory is allowed."""
    fake_temp = tmp_path / "fake_temp"
    fake_temp.mkdir()

    with patch("tempfile.gettempdir", return_value=str(fake_temp)):
        tmp_file = fake_temp / "temp_brief.docx"
        with open(tmp_file, "w") as f:
            f.write("content")
        dominion._validate_brief_path(str(tmp_file))

def test_validate_brief_path_invalid_outside(dominion, tmp_path):
    """Test that a file outside allowed directories raises ValueError."""
    fake_temp = tmp_path / "fake_system_temp"
    fake_temp.mkdir()

    outside_dir = tmp_path / "outside_data"
    outside_dir.mkdir()
    invalid_file = outside_dir / "secret.txt"
    with open(invalid_file, "w") as f:
        f.write("secret content")

    with patch("tempfile.gettempdir", return_value=str(fake_temp)):
        with pytest.raises(ValueError, match="Access denied"):
            dominion._validate_brief_path(str(invalid_file))

def test_validate_brief_path_non_existent(dominion):
    """Test that a non-existent file raises ValueError."""
    non_existent_file = os.path.join(dominion.case_context.base_path, "ghost.docx")

    with pytest.raises(ValueError, match="File not found"):
        dominion._validate_brief_path(non_existent_file)

def test_validate_brief_path_directory(dominion):
    """Test that a directory path raises ValueError."""
    case_dir = dominion.case_context.base_path
    os.makedirs(case_dir, exist_ok=True)

    with pytest.raises(ValueError, match="Path is not a file"):
        dominion._validate_brief_path(case_dir)

def test_validate_brief_path_traversal(dominion, tmp_path):
    """Test that path traversal attempts are caught."""
    outside_dir = tmp_path / "hacker"
    outside_dir.mkdir()
    secret_file = outside_dir / "passwd"
    with open(secret_file, "w") as f:
        f.write("root:x:0:0:root:/root:/bin/bash")

    case_dir = dominion.case_context.base_path
    os.makedirs(case_dir, exist_ok=True)

    fake_temp = tmp_path / "fake_system_temp"
    fake_temp.mkdir()

    traversal_path = os.path.join(case_dir, "..", "hacker", "passwd")

    assert os.path.abspath(traversal_path) == str(secret_file)

    with patch("tempfile.gettempdir", return_value=str(fake_temp)):
        with pytest.raises(ValueError, match="Access denied"):
            dominion._validate_brief_path(traversal_path)
