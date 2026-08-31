"""Add document upload metadata.

Revision ID: 20260824_0004
Revises: 20260823_0003
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0004"
down_revision: str | None = "20260823_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("domain_id", sa.Uuid(), nullable=True),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=4), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("object_storage_key", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("upload_status", sa.String(length=6), nullable=False),
        sa.Column("processing_status", sa.String(length=7), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("file_size > 0", name="ck_documents_file_size_positive"),
        sa.CheckConstraint(
            "char_length(checksum_sha256) = 64",
            name="ck_documents_checksum_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domains.id"], name="fk_documents_domain_id_domains"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], name="fk_documents_uploaded_by_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("object_storage_key", name="uq_documents_object_storage_key"),
    )
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"])
    op.create_index("ix_documents_domain_id", "documents", ["domain_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_domain_id", table_name="documents")
    op.drop_index("ix_documents_checksum_sha256", table_name="documents")
    op.drop_table("documents")
