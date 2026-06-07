"""Schemas Pydantic para grupos de despesa."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupBase(BaseModel):
    name: str = Field(..., max_length=80, description="Nome único do grupo")
    description: str | None = Field(None, description="Descrição do grupo — ajuda na classificação automática")
    sort_order: int | None = Field(None, description="Ordem de exibição")
    active: bool = Field(True, description="Se o grupo está ativo")


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = Field(None, max_length=80)
    description: str | None = None
    sort_order: int | None = None
    active: bool | None = None


class GroupOut(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
