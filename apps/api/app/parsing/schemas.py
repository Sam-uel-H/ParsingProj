from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.jobs.schemas import TaskProgress
from app.parsing.models import ParsingJobStatus, ResultValidationStatus
from app.templates.models import ColumnType


class ParsingJobCreate(BaseModel):
    document_id: uuid.UUID
    template_id: uuid.UUID
    confirm_domain_override: bool = False
    idempotency_key: uuid.UUID | None = None
    strategy: Literal["per_column", "batch"] | None = None


class ParsingResultRead(BaseModel):
    id: uuid.UUID
    template_column_id: uuid.UUID
    column_name: str
    column_type: ColumnType
    enum_values: list[str] | None
    raw_output: str | None
    canonical_value: str | None
    reviewed_value: str | None
    current_value: str | None
    validation_status: ResultValidationStatus
    validation_message: str | None
    confidence: float | None
    retry_count: int
    human_verified: bool
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None


class ParsingJobRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    status: ParsingJobStatus
    domain_override: bool
    started_by_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    results: list[ParsingResultRead]
    document_extraction_id: uuid.UUID | None = None
    strategy: str = "per_column"
    progress: TaskProgress | None = None


class ParsingResultCorrection(BaseModel):
    value: str | int | float | bool | None
