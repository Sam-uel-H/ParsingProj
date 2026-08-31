from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.parsing.models import ParsingJobStatus, ResultValidationStatus


class ParsingJobCreate(BaseModel):
    document_id: uuid.UUID
    template_id: uuid.UUID
    confirm_domain_override: bool = False


class ParsingResultRead(BaseModel):
    id: uuid.UUID
    template_column_id: uuid.UUID
    column_name: str
    raw_output: str | None
    canonical_value: str | None
    validation_status: ResultValidationStatus
    validation_message: str | None
    confidence: float | None
    retry_count: int


class ParsingJobRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    template_version_id: uuid.UUID
    status: ParsingJobStatus
    domain_override: bool
    started_by_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    results: list[ParsingResultRead]
