"""Torna budget_items.description nullable

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("budget_items", "description", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("budget_items", "description", existing_type=sa.Text(), nullable=False)
