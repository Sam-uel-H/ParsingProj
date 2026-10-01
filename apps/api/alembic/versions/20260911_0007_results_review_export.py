"""Add Phase 6 result review fields.

Revision ID: 20260911_0007
Revises: 20260824_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_0007"
down_revision: str | None = "20260824_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parsing_results", sa.Column("reviewed_value", sa.Text(), nullable=True))
    op.add_column(
        "parsing_results",
        sa.Column("human_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("parsing_results", sa.Column("reviewed_by_id", sa.Uuid(), nullable=True))
    op.add_column(
        "parsing_results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        "parsing_results_reviewed_by_id_fkey",
        "parsing_results",
        "users",
        ["reviewed_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "parsing_results_reviewed_by_id_fkey", "parsing_results", type_="foreignkey"
    )
    op.drop_column("parsing_results", "reviewed_at")
    op.drop_column("parsing_results", "reviewed_by_id")
    op.drop_column("parsing_results", "human_verified")
    op.drop_column("parsing_results", "reviewed_value")
