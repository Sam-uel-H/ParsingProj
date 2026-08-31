"""Add canonical document extraction and preview data.

Revision ID: 20260824_0005
Revises: 20260824_0004
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0005"
down_revision: str | None = "20260824_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "processing_status",
        existing_type=sa.String(length=7),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=True),
        sa.Column("provider_version", sa.String(length=100), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_document_extractions_document_id_documents"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_extractions"),
    )
    op.create_index("ix_document_extractions_document_id", "document_extractions", ["document_id"])
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("preview_object_key", sa.String(length=500), nullable=False),
        sa.Column("preview_content_type", sa.String(length=100), nullable=False),
        sa.CheckConstraint("page_number >= 1", name="ck_document_pages_page_number_positive"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_document_pages_dimensions_positive"
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["document_extractions.id"],
            name="fk_document_pages_extraction_id_document_extractions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_pages"),
        sa.UniqueConstraint(
            "extraction_id", "page_number", name="uq_document_pages_extraction_page_number"
        ),
    )
    op.create_index("ix_document_pages_extraction_id", "document_pages", ["extraction_id"])
    op.create_table(
        "document_text_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reading_order", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "reading_order >= 0", name="ck_document_text_blocks_reading_order_nonnegative"
        ),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end >= char_start",
            name="ck_document_text_blocks_offsets_valid",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_document_text_blocks_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["document_pages.id"],
            name="fk_document_text_blocks_page_id_document_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_text_blocks"),
    )
    op.create_index("ix_document_text_blocks_page_id", "document_text_blocks", ["page_id"])
    op.add_column("documents", sa.Column("active_extraction_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_documents_active_extraction_id_document_extractions"),
        "documents",
        "document_extractions",
        ["active_extraction_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_active_extraction_id_document_extractions", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "active_extraction_id")
    op.drop_index("ix_document_text_blocks_page_id", table_name="document_text_blocks")
    op.drop_table("document_text_blocks")
    op.drop_index("ix_document_pages_extraction_id", table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_index("ix_document_extractions_document_id", table_name="document_extractions")
    op.drop_table("document_extractions")
    op.alter_column(
        "documents",
        "processing_status",
        existing_type=sa.String(length=10),
        type_=sa.String(length=7),
        existing_nullable=False,
    )
