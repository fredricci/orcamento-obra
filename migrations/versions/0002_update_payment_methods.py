"""Atualiza payment_method_enum: remove 'credito', adiciona 'credito_avista' e 'credito_parcelado'

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar novos valores ao enum
    op.execute("ALTER TYPE payment_method_enum ADD VALUE IF NOT EXISTS 'credito_avista'")
    op.execute("ALTER TYPE payment_method_enum ADD VALUE IF NOT EXISTS 'credito_parcelado'")
    # Nota: PostgreSQL não permite remover valores de um enum.
    # Dados existentes com 'credito' continuam válidos no banco.
    # A aplicação não oferece mais 'credito' como opção.


def downgrade() -> None:
    # Não é possível remover valores de enum no PostgreSQL sem recriar o tipo.
    pass
