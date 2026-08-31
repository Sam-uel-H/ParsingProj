"""Create Phase 1 domain and template foundation.

Revision ID: 20260823_0002
Revises: 20260817_0001
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0002"
down_revision: str | None = "20260817_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

template_version_status = postgresql.ENUM(
    "draft", "published", name="template_version_status", create_type=False
)
column_type = postgresql.ENUM(
    "string",
    "integer",
    "decimal",
    "currency",
    "date",
    "boolean",
    "enum",
    name="column_type",
    create_type=False,
)


def attribution_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def add_attribution_foreign_keys(table_name: str) -> None:
    op.create_foreign_key(
        f"fk_{table_name}_created_by_id_users",
        table_name,
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        f"fk_{table_name}_updated_by_id_users",
        table_name,
        "users",
        ["updated_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    template_version_status.create(op.get_bind(), checkfirst=True)
    column_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *attribution_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_domains"),
        sa.UniqueConstraint("name", name="uq_domains_name"),
    )
    add_attribution_foreign_keys("domains")

    op.create_table(
        "templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("domain_id", sa.Uuid(), nullable=False),
        *attribution_columns(),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domains.id"], name="fk_templates_domain_id_domains", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_templates"),
    )
    add_attribution_foreign_keys("templates")
    op.create_index("ix_templates_domain_id", "templates", ["domain_id"])

    op.create_table(
        "template_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", template_version_status, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *attribution_columns(),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["templates.id"],
            name="fk_template_versions_template_id_templates",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_template_versions"),
        sa.UniqueConstraint(
            "template_id", "version_number", name="uq_template_versions_template_version_number"
        ),
    )
    add_attribution_foreign_keys("template_versions")
    op.create_index("ix_template_versions_template_id", "template_versions", ["template_id"])

    op.create_table(
        "template_columns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("column_type", column_type, nullable=False),
        sa.Column(
            "enum_values",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        *attribution_columns(),
        sa.CheckConstraint("display_order >= 0", name="display_order_nonnegative"),
        sa.CheckConstraint(
            "(column_type = 'enum' AND enum_values IS NOT NULL) OR "
            "(column_type <> 'enum' AND enum_values IS NULL)",
            name="enum_values_match_column_type",
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["template_versions.id"],
            name="fk_template_columns_template_version_id_template_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_template_columns"),
        sa.UniqueConstraint(
            "template_version_id",
            "name",
            name="uq_template_columns_template_version_column_name",
        ),
    )
    add_attribution_foreign_keys("template_columns")
    op.create_index(
        "ix_template_columns_version_order",
        "template_columns",
        ["template_version_id", "display_order"],
    )


def downgrade() -> None:
    op.drop_table("template_columns")
    op.drop_table("template_versions")
    op.drop_table("templates")
    op.drop_table("domains")
    op.drop_table("users")
    column_type.drop(op.get_bind(), checkfirst=True)
    template_version_status.drop(op.get_bind(), checkfirst=True)
