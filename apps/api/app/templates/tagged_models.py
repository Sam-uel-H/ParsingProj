from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class TaggedExample(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tagged_examples"
    __table_args__ = (
        UniqueConstraint(
            "template_column_id",
            "document_extraction_id",
            name="uq_tagged_examples_column_extraction",
        ),
        CheckConstraint("page_number >= 1", name="page_number_positive"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="offsets_valid"),
        Index("ix_tagged_examples_document_extraction_id", "document_extraction_id"),
        Index("ix_tagged_examples_document_id", "document_id"),
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
    tagged_value: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    rectangles: Mapped[list[dict[str, float]]] = mapped_column(JSON, nullable=False)
    text_block_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
