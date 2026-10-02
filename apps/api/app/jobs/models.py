from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

ACTIVE_STATES = ("queued", "extracting", "parsing")


class BackgroundTask(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        CheckConstraint(
            "(extraction_id IS NOT NULL AND parsing_job_id IS NULL) OR "
            "(extraction_id IS NULL AND parsing_job_id IS NOT NULL)",
            name="one_target",
        ),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts_valid"),
        CheckConstraint(
            "completed_units >= 0 AND total_units >= completed_units", name="progress_valid"
        ),
        Index("ix_background_tasks_dispatch", "state", "available_at", "dispatched_at"),
    )

    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="CASCADE"), unique=True
    )
    parsing_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parsing_jobs.id", ondelete="CASCADE"), unique=True
    )
    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
