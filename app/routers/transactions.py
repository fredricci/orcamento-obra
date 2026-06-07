"""Endpoints CRUD para transactions (lançamentos realizados)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.group import Group
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


async def _validate_group(db: AsyncSession, group_id: uuid.UUID) -> None:
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Grupo {group_id} não encontrado",
        )


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    group_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    limit: int | None = Query(None, gt=0, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[Transaction]:
    stmt = select(Transaction)
    if group_id:
        stmt = stmt.where(Transaction.group_id == group_id)
    if start_date:
        stmt = stmt.where(Transaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(Transaction.transaction_date <= end_date)
    stmt = stmt.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=list[TransactionOut], status_code=status.HTTP_201_CREATED)
async def create_transactions(
    payload: list[TransactionCreate],
    db: AsyncSession = Depends(get_db),
) -> list[Transaction]:
    """Cria uma ou mais transactions. Aceita array."""
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload não pode ser vazio",
        )

    # Validate all groups upfront
    group_ids = {p.group_id for p in payload}
    for gid in group_ids:
        await _validate_group(db, gid)

    transactions = []
    for item in payload:
        txn = Transaction(**item.model_dump())
        db.add(txn)
        transactions.append(txn)

    await db.commit()
    for txn in transactions:
        await db.refresh(txn)
    return transactions


@router.put("/{txn_id}", response_model=TransactionOut)
async def update_transaction(
    txn_id: uuid.UUID,
    payload: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
) -> Transaction:
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")

    updates = payload.model_dump(exclude_unset=True)
    if "group_id" in updates:
        await _validate_group(db, updates["group_id"])

    for field, value in updates.items():
        setattr(txn, field, value)

    await db.commit()
    await db.refresh(txn)
    return txn


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transação não encontrada")
    await db.delete(txn)
    await db.commit()
