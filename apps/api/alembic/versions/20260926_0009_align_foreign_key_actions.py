"""Align explicit foreign-key actions with ORM metadata.

Revision ID: 20260926_0009
Revises: 20260925_0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260926_0009"
down_revision: str | None = "20260925_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_foreign_keys(ondelete="RESTRICT")


def downgrade() -> None:
    _replace_foreign_keys(ondelete=None)


def _replace_foreign_keys(ondelete: str | None) -> None:
    constraints = (
        (
            "fk_documents_domain_id_domains",
            "documents",
            "domains",
            ["domain_id"],
            ["id"],
        ),
        (
            "fk_documents_uploaded_by_id_users",
            "documents",
            "users",
            ["uploaded_by_id"],
            ["id"],
        ),
        (
            "fk_document_extractions_document_id_documents",
            "document_extractions",
            "documents",
            ["document_id"],
            ["id"],
        ),
    )
    for name, source, target, local_columns, remote_columns in constraints:
        op.drop_constraint(name, source, type_="foreignkey")
        op.create_foreign_key(
            name,
            source,
            target,
            local_columns,
            remote_columns,
            ondelete=ondelete,
        )
