"""Add core parsing jobs, results, and LLM invocations.

Revision ID: 20260824_0006
Revises: 20260824_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0006"
down_revision: str | None = "20260824_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parsing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(23), nullable=False),
        sa.Column("domain_override", sa.Boolean(), nullable=False),
        sa.Column("started_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["template_versions.id"]),
        sa.ForeignKeyConstraint(["started_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "parsing_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parsing_job_id", sa.Uuid(), nullable=False),
        sa.Column("template_column_id", sa.Uuid(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("canonical_value", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(12), nullable=False),
        sa.Column("validation_message", sa.String(1000), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parsing_job_id"], ["parsing_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_column_id"], ["template_columns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parsing_job_id", "template_column_id"),
    )
    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parsing_job_id", sa.Uuid(), nullable=False),
        sa.Column("template_column_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["parsing_job_id"], ["parsing_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_column_id"], ["template_columns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_invocations")
    op.drop_table("parsing_results")
    op.drop_table("parsing_jobs")
