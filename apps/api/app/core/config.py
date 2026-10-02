from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "Document Parsing System API"
    app_version: str = "1.1.0"
    environment: Literal["development", "test", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "postgresql+psycopg://parsing:parsing@localhost:5432/parsing"
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_size_bytes: int = Field(default=25 * 1024 * 1024, ge=1)
    object_storage_path: Path = Path(__file__).resolve().parents[4] / ".local-storage"
    extraction_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    validation_retry_limit: int = Field(default=2, ge=0, le=10)
    redis_url: str = "redis://localhost:6379/0"
    job_max_attempts: int = Field(default=4, ge=1, le=10)
    job_retry_base_seconds: float = Field(default=2, gt=0)
    job_retry_max_seconds: float = Field(default=300, gt=0)
    parsing_concurrency: int = Field(default=4, ge=1, le=16)
    parsing_strategy: Literal["per_column", "batch"] = "per_column"
    parsing_batch_size: int = Field(default=5, ge=1, le=20)
    parsing_context_characters: int = Field(default=100_000, ge=4096)
    performance_sla_seconds: float = Field(default=30, gt=0)
    llm_provider: Literal["fake"] = "fake"
    document_extraction_provider: Literal["local"] = "local"
    object_storage_provider: Literal["filesystem"] = "filesystem"
    development_user_id: uuid.UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
    development_user_email: str = "developer@example.local"
    development_user_name: str = "Development User"


@lru_cache
def get_settings() -> Settings:
    return Settings()
