from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TemplateVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ColumnType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    CURRENCY = "currency"
    DATE = "date"
    BOOLEAN = "boolean"
    ENUM = "enum"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class Template(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_templates_domain_archived_updated", "domain_id", "archived_at", "updated_at"),
        Index("ix_templates_created_by_id", "created_by_id"),
        Index("ix_templates_archived_at", "archived_at"),
    )

    domain_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class TemplateVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version_number",
            name="uq_template_versions_template_version_number",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        CheckConstraint(
            "(status = 'draft' AND published_at IS NULL AND published_by_id IS NULL) OR "
            "(status = 'published' AND published_at IS NOT NULL AND published_by_id IS NOT NULL)",
            name="publication_metadata_matches_status",
        ),
        Index(
            "ix_template_versions_template_status_version",
            "template_id",
            "status",
            "version_number",
        ),
        Index("ix_template_versions_status_name", "status", "name"),
        Index("ix_template_versions_created_by_id", "created_by_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TemplateVersionStatus] = mapped_column(
        Enum(
            TemplateVersionStatus,
            name="template_version_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=TemplateVersionStatus.DRAFT,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class TemplateColumn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "template_columns"
    __table_args__ = (
        UniqueConstraint(
            "template_version_id",
            "name",
            name="uq_template_columns_template_version_column_name",
        ),
        CheckConstraint("display_order >= 0", name="display_order_nonnegative"),
        CheckConstraint(
            "(column_type = 'enum' AND enum_values IS NOT NULL) OR "
            "(column_type <> 'enum' AND enum_values IS NULL)",
            name="enum_values_match_column_type",
        ),
        Index("ix_template_columns_version_order", "template_version_id", "display_order"),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_type: Mapped[ColumnType] = mapped_column(
        Enum(ColumnType, name="column_type", values_callable=enum_values), nullable=False
    )
    enum_values: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
