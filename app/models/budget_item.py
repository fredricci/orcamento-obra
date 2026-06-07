"""Model de item de orçamento previsto."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Priority(str, enum.Enum):
    alta = "alta"
    media = "media"
    baixa = "baixa"


class BudgetItem(Base):
    """Item de orçamento previsto — múltiplos por grupo são normais."""

    __tablename__ = "budget_items"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum", create_constraint=False),
        nullable=False,
    )
    planned_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    group: Mapped["Group"] = relationship("Group", back_populates="budget_items")  # noqa: F821

    __table_args__ = (Index("ix_budget_items_group_id", "group_id"),)

    def __repr__(self) -> str:
        return f"<BudgetItem id={self.id} group_id={self.group_id} value={self.planned_value}>"
