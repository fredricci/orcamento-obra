"""Endpoints de dashboard — resumo, por grupo e por prioridade."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.budget_item import BudgetItem, Priority
from app.models.group import Group
from app.models.transaction import Transaction

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _fmt(value: Decimal | None) -> str:
    """Formata valor monetário como string decimal com 2 casas."""
    if value is None:
        return "0.00"
    return f"{Decimal(value):.2f}"


@router.get("/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> dict:
    # Total planned (only active groups)
    planned_q = select(func.coalesce(func.sum(BudgetItem.planned_value), 0)).join(
        Group, BudgetItem.group_id == Group.id
    ).where(Group.active == True)  # noqa: E712
    total_planned = (await db.execute(planned_q)).scalar()

    # Total realized (only active groups)
    realized_q = select(func.coalesce(func.sum(Transaction.value), 0)).join(
        Group, Transaction.group_id == Group.id
    ).where(Group.active == True)  # noqa: E712
    total_realized = (await db.execute(realized_q)).scalar()

    total_planned = Decimal(str(total_planned))
    total_realized = Decimal(str(total_realized))
    balance = total_planned - total_realized
    percent = float(total_realized / total_planned) if total_planned else 0.0

    # Groups over budget
    planned_sub = (
        select(
            BudgetItem.group_id,
            func.coalesce(func.sum(BudgetItem.planned_value), 0).label("planned"),
        )
        .group_by(BudgetItem.group_id)
        .subquery()
    )
    realized_sub = (
        select(
            Transaction.group_id,
            func.coalesce(func.sum(Transaction.value), 0).label("realized"),
        )
        .group_by(Transaction.group_id)
        .subquery()
    )
    over_q = (
        select(Group.name)
        .join(planned_sub, Group.id == planned_sub.c.group_id)
        .join(realized_sub, Group.id == realized_sub.c.group_id)
        .where(Group.active == True)  # noqa: E712
        .where(realized_sub.c.realized > planned_sub.c.planned)
    )
    over_result = await db.execute(over_q)
    groups_over = [row[0] for row in over_result.all()]

    return {
        "total_planned": _fmt(total_planned),
        "total_realized": _fmt(total_realized),
        "balance": _fmt(balance),
        "percent_executed": round(percent, 3),
        "groups_over_budget": groups_over,
    }


@router.get("/by-group")
async def dashboard_by_group(db: AsyncSession = Depends(get_db)) -> list[dict]:
    planned_sub = (
        select(
            BudgetItem.group_id,
            func.coalesce(func.sum(BudgetItem.planned_value), 0).label("planned"),
        )
        .group_by(BudgetItem.group_id)
        .subquery()
    )
    realized_sub = (
        select(
            Transaction.group_id,
            func.coalesce(func.sum(Transaction.value), 0).label("realized"),
        )
        .group_by(Transaction.group_id)
        .subquery()
    )

    stmt = (
        select(
            Group.id,
            Group.name,
            func.coalesce(planned_sub.c.planned, 0).label("planned"),
            func.coalesce(realized_sub.c.realized, 0).label("realized"),
        )
        .outerjoin(planned_sub, Group.id == planned_sub.c.group_id)
        .outerjoin(realized_sub, Group.id == realized_sub.c.group_id)
        .where(Group.active == True)  # noqa: E712
        .order_by(Group.sort_order, Group.name)
    )
    rows = (await db.execute(stmt)).all()

    result = []
    for row in rows:
        planned = Decimal(str(row.planned))
        realized = Decimal(str(row.realized))
        balance = planned - realized
        pct = float(realized / planned) if planned else 0.0
        result.append({
            "group_id": str(row.id),
            "group_name": row.name,
            "planned": _fmt(planned),
            "realized": _fmt(realized),
            "balance": _fmt(balance),
            "percent_executed": round(pct, 3),
            "is_over_budget": realized > planned,
        })
    return result


@router.get("/by-priority")
async def dashboard_by_priority(db: AsyncSession = Depends(get_db)) -> list[dict]:
    stmt = (
        select(
            BudgetItem.priority,
            func.coalesce(func.sum(BudgetItem.planned_value), 0).label("planned"),
            func.count(BudgetItem.id).label("items_count"),
        )
        .join(Group, BudgetItem.group_id == Group.id)
        .where(Group.active == True)  # noqa: E712
        .group_by(BudgetItem.priority)
    )
    rows = (await db.execute(stmt)).all()

    # Build a dict so we always return all 3 priorities
    by_prio = {r.priority: r for r in rows}
    result = []
    for p in [Priority.alta, Priority.media, Priority.baixa]:
        r = by_prio.get(p)
        result.append({
            "priority": p.value,
            "planned": _fmt(r.planned if r else 0),
            "items_count": r.items_count if r else 0,
        })
    return result
