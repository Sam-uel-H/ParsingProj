"""Add Phase 2 publishing metadata and optimistic concurrency.

Revision ID: 20260823_0003
Revises: 20260823_0002
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_0003"
down_revision: str | None = "20260823_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_versions",
        sa.Column("lock_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "template_versions",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "template_versions",
        sa.Column("published_by_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_template_versions_published_by_id_users",
        "template_versions",
        "users",
        ["published_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "lock_version_positive",
        "template_versions",
        "lock_version >= 1",
    )
    op.create_check_constraint(
        "publication_metadata_matches_status",
        "template_versions",
        "(status = 'draft' AND published_at IS NULL AND published_by_id IS NULL) OR "
        "(status = 'published' AND published_at IS NOT NULL AND published_by_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_template_versions_publication_metadata_matches_status"),
        "template_versions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_template_versions_lock_version_positive"),
        "template_versions",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_template_versions_published_by_id_users"),
        "template_versions",
        type_="foreignkey",
    )
    op.drop_column("template_versions", "published_by_id")
    op.drop_column("template_versions", "published_at")
    op.drop_column("template_versions", "lock_version")
