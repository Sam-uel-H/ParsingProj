"""Store prompt-helper examples against exact extraction versions.

Revision ID: 20260927_0011
Revises: 20260926_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927_0011"
down_revision: str | None = "20260926_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tagged_examples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_column_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_extraction_id", sa.Uuid(), nullable=False),
        sa.Column("tagged_value", sa.Text(), nullable=False),
        sa.Column("expected_value", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("rectangles", sa.JSON(), nullable=False),
        sa.Column("text_block_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("page_number >= 1", name="ck_tagged_examples_page_number_positive"),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start", name="ck_tagged_examples_offsets_valid"
        ),
        sa.ForeignKeyConstraint(
            ["template_column_id"],
            ["template_columns.id"],
            name="fk_tagged_examples_template_column_id_template_columns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_tagged_examples_document_id_documents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_extraction_id"],
            ["document_extractions.id"],
            name="fk_tagged_examples_document_extraction_id_document_extractions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_tagged_examples_created_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tagged_examples"),
        sa.UniqueConstraint(
            "template_column_id",
            "document_extraction_id",
            name="uq_tagged_examples_column_extraction",
        ),
    )
    op.create_index(
        "ix_tagged_examples_document_extraction_id", "tagged_examples", ["document_extraction_id"]
    )
    op.create_index("ix_tagged_examples_document_id", "tagged_examples", ["document_id"])


def downgrade() -> None:
    op.drop_table("tagged_examples")
