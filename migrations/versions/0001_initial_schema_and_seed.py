"""Initial schema: groups, budget_items, transactions + seed dos 24 grupos

Revision ID: 0001
Revises:
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GRUPOS_SEED = [
    "Obra Civil",
    "Limpeza",
    "Ar Condicionado",
    "Iluminação Técnica",
    "Iluminação Decorativa",
    "Acabamentos Elétricos",
    "Louças e Metais",
    "Piso Porcelanato",
    "Revestimento",
    "Piso de Madeira",
    "Marcenaria",
    "Aquecedor a Gás",
    "Fechamento Varanda",
    "Vidraçaria",
    "Acessórios",
    "Churrasqueira",
    "Automação",
    "Chopeira",
    "Eletrodomésticos",
    "Mobílias",
    "Cortinas",
    "Decoração",
    "Varal",
    "Fechadura Digital",
]


def upgrade() -> None:
    # ---- Tabela groups ----
    op.create_table(
        "groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(80), unique=True, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ---- Tabela budget_items ----
    op.create_table(
        "budget_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier", sa.String(120), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("priority", sa.Enum("alta", "media", "baixa", name="priority_enum", create_type=True), nullable=False),
        sa.Column("planned_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_budget_items_group_id", "budget_items", ["group_id"])

    # ---- Tabela transactions ----
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=True),
        sa.Column("supplier", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("pix", "credito", "debito", "boleto", "transferencia", "dinheiro",
                    name="payment_method_enum", create_type=True),
            nullable=True,
        ),
        sa.Column("observation", sa.Text, nullable=True),
        sa.Column(
            "source",
            sa.Enum("chat", "manual", name="transaction_source_enum", create_type=True),
            nullable=True,
        ),
        sa.Column(
            "input_type",
            sa.Enum("image", "pdf", "audio", "text", "manual", name="input_type_enum", create_type=True),
            nullable=True,
        ),
        sa.Column("receipt_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_group_date", "transactions", ["group_id", "transaction_date"])
    op.create_index("ix_transactions_date", "transactions", ["transaction_date"])

    # ---- Seed dos 24 grupos ----
    now = datetime.now(timezone.utc)
    groups_table = sa.table(
        "groups",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        groups_table,
        [
            {
                "id": uuid.uuid4(),
                "name": nome,
                "sort_order": idx + 1,
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
            for idx, nome in enumerate(GRUPOS_SEED)
        ],
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("budget_items")
    op.drop_table("groups")
    op.execute("DROP TYPE IF EXISTS input_type_enum")
    op.execute("DROP TYPE IF EXISTS transaction_source_enum")
    op.execute("DROP TYPE IF EXISTS payment_method_enum")
    op.execute("DROP TYPE IF EXISTS priority_enum")
