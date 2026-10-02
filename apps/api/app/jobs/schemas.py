from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    state: str
    attempts: int
    max_attempts: int
    completed_units: int
    total_units: int
    error_code: str | None
    error_message: str | None
    retryable: bool
    available_at: datetime
