from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeneratePromptRequest(BaseModel):
    template_column_id: uuid.UUID
    document_id: uuid.UUID


class EditPromptRequest(BaseModel):
    edited_prompt: str = Field(min_length=1, max_length=10000)

    @field_validator("edited_prompt")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt must not be blank.")
        return value


class AcceptPromptRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


class PromptDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_column_id: uuid.UUID
    document_id: uuid.UUID
    document_extraction_id: uuid.UUID
    expected_value: str
    suggested_prompt: str
    edited_prompt: str
    dry_runs: list[dict[str, Any]]
    accepted: bool
    provider_name: str
    model_name: str
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
