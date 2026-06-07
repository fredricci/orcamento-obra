"""Endpoints CRUD para budget items (orçamento previsto)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.budget_item import BudgetItem
from app.models.group import Group
from app.schemas.budget_item import BudgetItemCreate, BudgetItemOut, BudgetItemUpdate

router = APIRouter(prefix="/api/v1/budget-items", tags=["budget-items"])


async def _validate_group(db: AsyncSession, group_id: uuid.UUID) -> None:
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Grupo {group_id} não encontrado",
        )


@router.get("", response_model=list[BudgetItemOut])
async def list_budget_items(
    group_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[BudgetItem]:
    stmt = select(BudgetItem)
    if group_id:
        stmt = stmt.where(BudgetItem.group_id == group_id)
    stmt = stmt.order_by(BudgetItem.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=BudgetItemOut, status_code=status.HTTP_201_CREATED)
async def create_budget_item(
    payload: BudgetItemCreate,
    db: AsyncSession = Depends(get_db),
) -> BudgetItem:
    await _validate_group(db, payload.group_id)
    item = BudgetItem(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=BudgetItemOut)
async def update_budget_item(
    item_id: uuid.UUID,
    payload: BudgetItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> BudgetItem:
    item = await db.get(BudgetItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")

    updates = payload.model_dump(exclude_unset=True)
    if "group_id" in updates:
        await _validate_group(db, updates["group_id"])

    for field, value in updates.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    item = await db.get(BudgetItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    await db.delete(item)
    await db.commit()
