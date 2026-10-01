"""Add MVP workflow constraints and indexes.

Revision ID: 20260925_0008
Revises: 20260911_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0008"
down_revision: str | None = "20260911_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_parsing_jobs_document_started", "parsing_jobs", ["document_id", "started_at"]
    )
    op.create_index(
        "ix_parsing_jobs_template_version_id", "parsing_jobs", ["template_version_id"]
    )
    op.create_check_constraint(
        "ck_parsing_results_retry_count_nonnegative", "parsing_results", "retry_count >= 0"
    )
    op.create_check_constraint(
        "ck_parsing_results_confidence_range",
        "parsing_results",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
    )
    op.create_index(
        "ix_parsing_results_job_validation",
        "parsing_results",
        ["parsing_job_id", "validation_status"],
    )
    op.create_unique_constraint(
        "uq_llm_invocations_job_column_attempt",
        "llm_invocations",
        ["parsing_job_id", "template_column_id", "attempt_number"],
    )
    op.create_check_constraint(
        "ck_llm_invocations_attempt_number_positive",
        "llm_invocations",
        "attempt_number >= 1",
    )
    op.create_index(
        "ix_llm_invocations_parsing_job_id", "llm_invocations", ["parsing_job_id"]
    )
    op.create_index(
        "ix_template_versions_template_status_version",
        "template_versions",
        ["template_id", "status", "version_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_template_versions_template_status_version", table_name="template_versions"
    )
    op.drop_index("ix_llm_invocations_parsing_job_id", table_name="llm_invocations")
    op.drop_constraint(
        "ck_llm_invocations_attempt_number_positive", "llm_invocations", type_="check"
    )
    op.drop_constraint(
        "uq_llm_invocations_job_column_attempt",
        "llm_invocations",
        type_="unique",
    )
    op.drop_index("ix_parsing_results_job_validation", table_name="parsing_results")
    op.drop_constraint(
        "ck_parsing_results_confidence_range", "parsing_results", type_="check"
    )
    op.drop_constraint(
        "ck_parsing_results_retry_count_nonnegative", "parsing_results", type_="check"
    )
    op.drop_index("ix_parsing_jobs_template_version_id", table_name="parsing_jobs")
    op.drop_index("ix_parsing_jobs_document_started", table_name="parsing_jobs")
