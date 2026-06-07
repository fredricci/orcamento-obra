"""Adiciona status em budget_items (ideia, orcado, contratado, concluido)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE item_status_enum AS ENUM ('ideia', 'orcado', 'contratado', 'concluido')")
    op.add_column(
        "budget_items",
        sa.Column(
            "status",
            sa.Enum("ideia", "orcado", "contratado", "concluido", name="item_status_enum", create_type=False),
            nullable=False,
            server_default="ideia",
        ),
    )


def downgrade() -> None:
    op.drop_column("budget_items", "status")
    op.execute("DROP TYPE IF EXISTS item_status_enum")
