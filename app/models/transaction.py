"""Model de lançamento realizado."""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentMethod(str, enum.Enum):
    pix = "pix"
    credito_avista = "credito_avista"
    credito_parcelado = "credito_parcelado"
    debito = "debito"
    boleto = "boleto"
    transferencia = "transferencia"
    dinheiro = "dinheiro"


class TransactionSource(str, enum.Enum):
    chat = "chat"
    manual = "manual"


class InputType(str, enum.Enum):
    image = "image"
    pdf = "pdf"
    audio = "audio"
    text = "text"
    manual = "manual"


class Transaction(Base):
    """Lançamento realizado — gasto efetivo em um grupo."""

    __tablename__ = "transactions"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum", create_constraint=False),
        nullable=True,
    )
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[TransactionSource | None] = mapped_column(
        Enum(TransactionSource, name="transaction_source_enum", create_constraint=False),
        nullable=True,
    )
    input_type: Mapped[InputType | None] = mapped_column(
        Enum(InputType, name="input_type_enum", create_constraint=False),
        nullable=True,
    )
    receipt_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    group: Mapped["Group"] = relationship("Group", back_populates="transactions")  # noqa: F821

    __table_args__ = (
        Index("ix_transactions_group_date", "group_id", "transaction_date"),
        Index("ix_transactions_date", "transaction_date"),
    )

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} supplier={self.supplier!r} value={self.value}>"
