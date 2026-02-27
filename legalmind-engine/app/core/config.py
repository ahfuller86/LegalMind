import os
from typing import List
from pydantic import BaseModel, Field

class Config(BaseModel):
    # Privacy & Security
    CLOUD_MODEL_ALLOWED: bool = Field(default=True, description="Allow sending data to cloud LLM providers")
    PHI_REDACTION_REQUIRED: bool = Field(default=False, description="Redact PHI before storage")
    EXPORT_RAW_EVIDENCE: bool = Field(default=True, description="Include raw evidence text in reports")

    # Models
    LLM_PROVIDER: str = Field(default="openai", description="litellm provider name (openai, anthropic, ollama)")
    LLM_MODEL_NAME: str = Field(default="gpt-4o", description="Model name for verification")
    EMBEDDING_PROVIDER: str = Field(default="sentence-transformers", description="embedding provider")

    # Audio Models
    WHISPER_MODEL_FAST: str = Field(default="tiny", description="Fast Whisper model for ingestion")
    WHISPER_MODEL_ACCURATE: str = Field(default="large", description="Accurate Whisper model for refinement")

    # Concurrency
    MAX_LLM_CONCURRENCY: int = 10
    MAX_IO_CONCURRENCY: int = 5
    MAX_CPU_CONCURRENCY: int = 4

    # System
    STORAGE_PATH: str = Field(default="./storage", description="Base storage path for cases")
    ALLOWED_INPUT_PATHS: List[str] = Field(default=["/tmp", "."], description="Allowed paths for file ingestion")
    BACKGROUND_TASK_ENABLED: bool = Field(default=True, description="Enable background maintenance tasks")

    class Config:
        env_prefix = "LEGALMIND_"

def load_config() -> Config:
    # In a real app, we might load from .env file here
    return Config(
        CLOUD_MODEL_ALLOWED=os.getenv("LEGALMIND_CLOUD_MODEL_ALLOWED", "true").lower() == "true",
        PHI_REDACTION_REQUIRED=os.getenv("LEGALMIND_PHI_REDACTION_REQUIRED", "false").lower() == "true",
        EXPORT_RAW_EVIDENCE=os.getenv("LEGALMIND_EXPORT_RAW_EVIDENCE", "true").lower() == "true",
        LLM_PROVIDER=os.getenv("LEGALMIND_LLM_PROVIDER", "openai"),
        LLM_MODEL_NAME=os.getenv("LEGALMIND_LLM_MODEL_NAME", "gpt-4o"),
        EMBEDDING_PROVIDER=os.getenv("LEGALMIND_EMBEDDING_PROVIDER", "sentence-transformers"),
        WHISPER_MODEL_FAST=os.getenv("LEGALMIND_WHISPER_MODEL_FAST", "tiny"),
        WHISPER_MODEL_ACCURATE=os.getenv("LEGALMIND_WHISPER_MODEL_ACCURATE", "large"),
        STORAGE_PATH=os.getenv("LEGALMIND_STORAGE_PATH", "./storage"),
        ALLOWED_INPUT_PATHS=os.getenv("LEGALMIND_ALLOWED_INPUT_PATHS", "/tmp,.").split(","),
        BACKGROUND_TASK_ENABLED=os.getenv("LEGALMIND_BACKGROUND_TASK_ENABLED", "true").lower() == "true",
    )
