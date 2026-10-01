"""Add complete template lifecycle metadata and indexes.

Revision ID: 20260926_0010
Revises: 20260926_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260926_0010"
down_revision: str | None = "20260926_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("templates", sa.Column("archived_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_templates_archived_by_id_users",
        "templates",
        "users",
        ["archived_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_templates_domain_archived_updated",
        "templates",
        ["domain_id", "archived_at", "updated_at"],
    )
    op.create_index("ix_templates_created_by_id", "templates", ["created_by_id"])
    op.create_index("ix_templates_archived_at", "templates", ["archived_at"])
    op.create_index(
        "ix_template_versions_status_name",
        "template_versions",
        ["status", "name"],
    )
    op.create_index(
        "ix_template_versions_created_by_id",
        "template_versions",
        ["created_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_versions_created_by_id", table_name="template_versions")
    op.drop_index("ix_template_versions_status_name", table_name="template_versions")
    op.drop_index("ix_templates_archived_at", table_name="templates")
    op.drop_index("ix_templates_created_by_id", table_name="templates")
    op.drop_index("ix_templates_domain_archived_updated", table_name="templates")
    op.drop_constraint("fk_templates_archived_by_id_users", "templates", type_="foreignkey")
    op.drop_column("templates", "archived_by_id")
    op.drop_column("templates", "archived_at")
