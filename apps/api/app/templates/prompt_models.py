from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class PromptDraft(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_drafts"
    __table_args__ = (
        Index(
            "ix_prompt_drafts_column_document_created",
            "template_column_id",
            "document_id",
            "created_at",
        ),
    )

    template_column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_columns.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False
    )
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="RESTRICT"), nullable=False
    )
    expected_value: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    edited_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    dry_runs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
