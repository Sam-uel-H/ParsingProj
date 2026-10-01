"""Persist generated prompts and dry-run history.

Revision ID: 20260928_0012
Revises: 20260927_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260928_0012"
down_revision: str | None = "20260927_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_column_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_extraction_id", sa.Uuid(), nullable=False),
        sa.Column("expected_value", sa.Text(), nullable=False),
        sa.Column("suggested_prompt", sa.Text(), nullable=False),
        sa.Column("edited_prompt", sa.Text(), nullable=False),
        sa.Column("dry_runs", sa.JSON(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["template_column_id"], ["template_columns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_extraction_id"], ["document_extractions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_drafts"),
    )
    op.create_index(
        "ix_prompt_drafts_column_document_created",
        "prompt_drafts",
        ["template_column_id", "document_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("prompt_drafts")
