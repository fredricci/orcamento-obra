"""Model do grupo de despesa."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Group(Base):
    """Grupo de despesa (ex: Obra Civil, Marcenaria, etc.)."""

    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relacionamentos (lazy por padrão, sem carregamento automático)
    budget_items: Mapped[list["BudgetItem"]] = relationship(  # noqa: F821
        "BudgetItem", back_populates="group", lazy="noload"
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        "Transaction", back_populates="group", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Group id={self.id} name={self.name!r} active={self.active}>"
