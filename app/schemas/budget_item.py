"""Schemas Pydantic para budget items."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.budget_item import Priority


class BudgetItemCreate(BaseModel):
    group_id: uuid.UUID
    supplier: str | None = Field(None, max_length=120)
    description: str
    priority: Priority
    planned_value: Decimal = Field(..., gt=0, decimal_places=2)


class BudgetItemUpdate(BaseModel):
    group_id: uuid.UUID | None = None
    supplier: str | None = Field(None, max_length=120)
    description: str | None = None
    priority: Priority | None = None
    planned_value: Decimal | None = Field(None, gt=0, decimal_places=2)


class BudgetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    supplier: str | None
    description: str
    priority: Priority
    planned_value: Decimal
    created_at: datetime
    updated_at: datetime
