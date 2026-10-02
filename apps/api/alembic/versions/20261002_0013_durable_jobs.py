"""Persist background tasks and pin parsing jobs to extraction versions."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_0013"
down_revision: str | None = "20260928_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_extractions", sa.Column("version_number", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE document_extractions e SET version_number = numbered.version
        FROM (SELECT id, row_number() OVER
              (PARTITION BY document_id ORDER BY started_at, id) AS version
              FROM document_extractions) numbered WHERE e.id = numbered.id
    """)
    op.alter_column("document_extractions", "version_number", nullable=False)
    op.create_unique_constraint(
        "uq_extractions_document_version", "document_extractions", ["document_id", "version_number"]
    )
    op.add_column("parsing_jobs", sa.Column("document_extraction_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_parsing_jobs_document_extraction_id_document_extractions",
        "parsing_jobs",
        "document_extractions",
        ["document_extraction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # Historical jobs only get a link when their document has exactly one successful extraction.
    op.execute("""
        UPDATE parsing_jobs j SET document_extraction_id = e.id
        FROM document_extractions e WHERE e.document_id = j.document_id AND e.status = 'SUCCEEDED'
        AND (SELECT count(*) FROM document_extractions x
             WHERE x.document_id = j.document_id AND x.status = 'SUCCEEDED') = 1
    """)
    op.add_column("parsing_jobs", sa.Column("idempotency_key", sa.Uuid(), nullable=True))
    op.add_column(
        "parsing_jobs",
        sa.Column("strategy", sa.String(20), nullable=False, server_default="per_column"),
    )
    op.alter_column("parsing_jobs", "strategy", server_default=None)
    op.create_unique_constraint(
        "uq_jobs_actor_idempotency", "parsing_jobs", ["started_by_id", "idempotency_key"]
    )
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_id", sa.Uuid(), nullable=True),
        sa.Column("parsing_job_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("completed_units", sa.Integer(), nullable=False),
        sa.Column("total_units", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["extraction_id"], ["document_extractions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsing_job_id"], ["parsing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("extraction_id"),
        sa.UniqueConstraint("parsing_job_id"),
        sa.CheckConstraint(
            "(extraction_id IS NOT NULL AND parsing_job_id IS NULL) OR "
            "(extraction_id IS NULL AND parsing_job_id IS NOT NULL)",
            name="one_target",
        ),
        sa.CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts_valid"),
        sa.CheckConstraint(
            "completed_units >= 0 AND total_units >= completed_units", name="progress_valid"
        ),
    )
    op.create_index(
        "ix_background_tasks_dispatch",
        "background_tasks",
        ["state", "available_at", "dispatched_at"],
    )


def downgrade() -> None:
    op.drop_table("background_tasks")
    op.drop_constraint("uq_jobs_actor_idempotency", "parsing_jobs", type_="unique")
    op.drop_column("parsing_jobs", "strategy")
    op.drop_column("parsing_jobs", "idempotency_key")
    op.drop_column("parsing_jobs", "document_extraction_id")
    op.drop_constraint("uq_extractions_document_version", "document_extractions", type_="unique")
    op.drop_column("document_extractions", "version_number")
