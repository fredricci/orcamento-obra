"""Schemas Pydantic para transactions."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.transaction import InputType, PaymentMethod, TransactionSource


class TransactionCreate(BaseModel):
    group_id: uuid.UUID
    transaction_date: date
    supplier: str = Field(..., max_length=120)
    description: str | None = None
    value: Decimal = Field(..., gt=0, decimal_places=2)
    payment_method: PaymentMethod
    observation: str | None = None
    source: TransactionSource = TransactionSource.manual
    input_type: InputType | None = None
    receipt_ref: str | None = Field(None, max_length=255)

    @field_validator("transaction_date")
    @classmethod
    def date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("transaction_date não pode ser no futuro")
        return v


class TransactionUpdate(BaseModel):
    group_id: uuid.UUID | None = None
    transaction_date: date | None = None
    supplier: str | None = Field(None, max_length=120)
    description: str | None = None
    value: Decimal | None = Field(None, gt=0, decimal_places=2)
    payment_method: PaymentMethod | None = None
    observation: str | None = None
    source: TransactionSource | None = None
    input_type: InputType | None = None
    receipt_ref: str | None = Field(None, max_length=255)

    @field_validator("transaction_date")
    @classmethod
    def date_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("transaction_date não pode ser no futuro")
        return v


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    transaction_date: date | None
    supplier: str
    description: str | None
    value: Decimal
    payment_method: PaymentMethod | None
    observation: str | None
    source: TransactionSource | None
    input_type: InputType | None
    receipt_ref: str | None
    created_at: datetime
    updated_at: datetime
