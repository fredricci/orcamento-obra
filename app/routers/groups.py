"""Endpoints CRUD para grupos de despesa."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.group import Group
from app.schemas.group import GroupCreate, GroupOut, GroupUpdate

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
async def list_groups(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[Group]:
    """Lista todos os grupos, ordenados por sort_order e nome."""
    stmt = select(Group)
    if not include_inactive:
        stmt = stmt.where(Group.active.is_(True))
    stmt = stmt.order_by(Group.sort_order.nullslast(), Group.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
) -> Group:
    """Cria um novo grupo de despesa."""
    # Verifica duplicidade
    existing = await db.execute(select(Group).where(Group.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um grupo com o nome '{payload.name}'",
        )
    group = Group(**payload.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.put("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
) -> Group:
    """Atualiza campos de um grupo existente."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != group.name:
        # Verifica conflito de nome
        existing = await db.execute(select(Group).where(Group.name == updates["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um grupo com o nome '{updates['name']}'",
            )
    for field, value in updates.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete: desativa o grupo (active=false)."""
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    group.active = False
    await db.commit()
