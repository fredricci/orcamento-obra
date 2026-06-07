"""Schemas Pydantic para budget items."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.budget_item import ItemStatus, Priority


class BudgetItemCreate(BaseModel):
    group_id: uuid.UUID
    supplier: str | None = Field(None, max_length=120)
    description: str | None = None
    priority: Priority
    planned_value: Decimal = Field(..., gt=0, decimal_places=2)
    status: ItemStatus = ItemStatus.ideia


class BudgetItemUpdate(BaseModel):
    group_id: uuid.UUID | None = None
    supplier: str | None = Field(None, max_length=120)
    description: str | None = None
    priority: Priority | None = None
    planned_value: Decimal | None = Field(None, gt=0, decimal_places=2)
    status: ItemStatus | None = None


class BudgetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    supplier: str | None
    description: str | None
    priority: Priority
    planned_value: Decimal
    status: ItemStatus
    created_at: datetime
    updated_at: datetime
