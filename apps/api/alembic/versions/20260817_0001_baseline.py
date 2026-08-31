"""Create the empty Phase 0 migration baseline.

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""

from collections.abc import Sequence

revision: str = "20260817_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the migration chain without creating Phase 1 entities."""


def downgrade() -> None:
    """Remove the empty baseline (no schema objects to drop)."""

