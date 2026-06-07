"""Rotas web (Jinja2 templates) — dashboard, grupos, previsto, realizado."""

import secrets
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.budget_item import BudgetItem, ItemStatus, Priority
from app.models.group import Group
from app.models.transaction import Transaction, PaymentMethod, TransactionSource

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


# --------------- Basic Auth ---------------

def _check_auth(request: Request) -> None:
    """Verifica basic auth. Levanta HTTPException 401 se falhar."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Orcamento de Obra"'},
        )
    import base64
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        user, password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Orcamento de Obra"'},
        )
    if not (
        secrets.compare_digest(user, settings.web_user)
        and secrets.compare_digest(password, settings.web_password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Orcamento de Obra"'},
        )


def _fmt(value: Decimal | float | None) -> str:
    if value is None:
        return "0,00"
    d = Decimal(str(value))
    # Format as Brazilian style: 1.234,56
    formatted = f"{d:,.2f}"
    # Swap . and , for BRL
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


# --------------- Dashboard ---------------

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    _check_auth(request)

    # Summary
    planned_q = (
        select(func.coalesce(func.sum(BudgetItem.planned_value), 0))
        .join(Group, BudgetItem.group_id == Group.id)
        .where(Group.active == True)  # noqa: E712
    )
    total_planned = Decimal(str((await db.execute(planned_q)).scalar()))

    realized_q = (
        select(func.coalesce(func.sum(Transaction.value), 0))
        .join(Group, Transaction.group_id == Group.id)
        .where(Group.active == True)  # noqa: E712
    )
    total_realized = Decimal(str((await db.execute(realized_q)).scalar()))

    balance = total_planned - total_realized
    pct = float(total_realized / total_planned * 100) if total_planned else 0.0

    summary = {
        "total_planned": _fmt(total_planned),
        "total_realized": _fmt(total_realized),
        "balance": _fmt(balance),
        "balance_negative": balance < 0,
        "percent_executed": f"{pct:.1f}",
    }

    # By priority
    prio_q = (
        select(
            BudgetItem.priority,
            func.coalesce(func.sum(BudgetItem.planned_value), 0).label("planned"),
            func.count(BudgetItem.id).label("items_count"),
        )
        .join(Group, BudgetItem.group_id == Group.id)
        .where(Group.active == True)  # noqa: E712
        .group_by(BudgetItem.priority)
    )
    prio_rows = (await db.execute(prio_q)).all()
    by_prio = {r.priority: r for r in prio_rows}
    priorities = []
    for p in [Priority.alta, Priority.media, Priority.baixa]:
        r = by_prio.get(p)
        priorities.append({
            "priority": p.value,
            "planned": _fmt(r.planned if r else 0),
            "items_count": r.items_count if r else 0,
        })

    # By group
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
    grp_q = (
        select(
            Group.name,
            func.coalesce(planned_sub.c.planned, 0).label("planned"),
            func.coalesce(realized_sub.c.realized, 0).label("realized"),
        )
        .outerjoin(planned_sub, Group.id == planned_sub.c.group_id)
        .outerjoin(realized_sub, Group.id == realized_sub.c.group_id)
        .where(Group.active == True)  # noqa: E712
        .order_by(Group.sort_order.nullslast(), Group.name)
    )
    grp_rows = (await db.execute(grp_q)).all()

    groups_data = []
    chart_labels = []
    chart_planned = []
    chart_realized = []
    for row in grp_rows:
        p = Decimal(str(row.planned))
        r = Decimal(str(row.realized))
        b = p - r
        pct_g = float(r / p * 100) if p else 0.0
        groups_data.append({
            "group_name": row.name,
            "planned": _fmt(p),
            "realized": _fmt(r),
            "balance": _fmt(b),
            "is_over_budget": r > p,
            "percent_display": f"{pct_g:.1f}",
        })
        chart_labels.append(row.name)
        chart_planned.append(float(p))
        chart_realized.append(float(r))

    return templates.TemplateResponse(request, "dashboard.html", {
        "active_page": "dashboard",
        "summary": summary,
        "priorities": priorities,
        "groups": groups_data,
        "chart_labels": chart_labels,
        "chart_planned": chart_planned,
        "chart_realized": chart_realized,
    })


# --------------- Grupos ---------------

async def _get_all_groups(db: AsyncSession, include_inactive: bool = True) -> list[Group]:
    stmt = select(Group)
    if not include_inactive:
        stmt = stmt.where(Group.active == True)  # noqa: E712
    stmt = stmt.order_by(Group.sort_order.nullslast(), Group.name)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/grupos", response_class=HTMLResponse)
async def grupos_page(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    _check_auth(request)
    groups = await _get_all_groups(db)
    return templates.TemplateResponse(request, "grupos.html", {
        "active_page": "grupos",
        "groups": groups,
    })


@router.post("/grupos", response_class=HTMLResponse)
async def create_group_web(
    request: Request,
    name: str = Form(...),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    group = Group(name=name, description=description or None, active=True)
    db.add(group)
    await db.commit()
    groups = await _get_all_groups(db)
    return templates.TemplateResponse(request, "partials/groups_rows.html", {
        "groups": groups,
    })


@router.put("/grupos/{group_id}", response_class=HTMLResponse)
async def update_group_web(
    request: Request,
    group_id: uuid.UUID,
    name: str = Form(...),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    group.name = name
    group.description = description or None
    await db.commit()
    groups = await _get_all_groups(db)
    return templates.TemplateResponse(request, "partials/groups_rows.html", {
        "groups": groups,
    })


@router.put("/grupos/{group_id}/toggle", response_class=HTMLResponse)
async def toggle_group_web(
    request: Request,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    group.active = not group.active
    await db.commit()
    groups = await _get_all_groups(db)
    return templates.TemplateResponse(request, "partials/groups_rows.html", {
        "groups": groups,
    })


@router.delete("/grupos/{group_id}", response_class=HTMLResponse)
async def delete_group_web(
    request: Request,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    group = await db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    try:
        await db.delete(group)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Não é possível excluir grupo com itens ou lançamentos vinculados")
    groups = await _get_all_groups(db)
    return templates.TemplateResponse(request, "partials/groups_rows.html", {
        "groups": groups,
    })


# --------------- Previsto ---------------

async def _budget_items_context(
    db: AsyncSession,
    filter_group: str | None = None,
    filter_priority: str | None = None,
    filter_status: str | None = None,
) -> dict:
    groups = await _get_all_groups(db, include_inactive=False)
    group_map = {g.id: g.name for g in groups}

    stmt = select(BudgetItem).join(Group, BudgetItem.group_id == Group.id).where(Group.active == True)  # noqa: E712
    if filter_group:
        stmt = stmt.where(BudgetItem.group_id == uuid.UUID(filter_group))
    if filter_priority:
        stmt = stmt.where(BudgetItem.priority == filter_priority)
    if filter_status:
        stmt = stmt.where(BudgetItem.status == filter_status)
    stmt = stmt.order_by(Group.sort_order.nullslast(), Group.name, BudgetItem.created_at)
    rows = list((await db.execute(stmt)).scalars().all())

    total = sum(Decimal(str(r.planned_value)) for r in rows)
    items = []
    for r in rows:
        items.append({
            "id": str(r.id),
            "group_id": str(r.group_id),
            "group_name": group_map.get(r.group_id, "?"),
            "supplier": r.supplier,
            "description": r.description,
            "priority": r.priority.value if r.priority else "",
            "status": r.status.value if r.status else "ideia",
            "planned_value": str(r.planned_value),
            "planned_value_fmt": _fmt(r.planned_value),
        })
    return {
        "groups": groups,
        "items": items,
        "total": _fmt(total),
        "filter_group": filter_group or "",
        "filter_priority": filter_priority or "",
        "filter_status": filter_status or "",
    }


@router.get("/previsto", response_class=HTMLResponse)
async def previsto_page(
    request: Request,
    group_id: str | None = Query(None),
    priority: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    ctx = await _budget_items_context(db, group_id, priority, status)
    return templates.TemplateResponse(request, "previsto.html", {
        "active_page": "previsto",
        **ctx,
    })


@router.post("/previsto", response_class=HTMLResponse)
async def create_budget_item_web(
    request: Request,
    group_id: uuid.UUID = Form(...),
    description: str | None = Form(None),
    priority: str = Form(...),
    planned_value: float = Form(...),
    supplier: str | None = Form(None),
    status: str = Form("ideia"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    item = BudgetItem(
        group_id=group_id,
        supplier=supplier or None,
        description=description or None,
        priority=Priority(priority),
        planned_value=planned_value,
        status=ItemStatus(status),
    )
    db.add(item)
    await db.commit()
    ctx = await _budget_items_context(db)
    return templates.TemplateResponse(request, "partials/budget_items_rows.html", {
        **ctx,
    })


@router.put("/previsto/{item_id}", response_class=HTMLResponse)
async def update_budget_item_web(
    request: Request,
    item_id: uuid.UUID,
    group_id: uuid.UUID = Form(...),
    description: str | None = Form(None),
    priority: str = Form(...),
    planned_value: float = Form(...),
    supplier: str | None = Form(None),
    status: str = Form("ideia"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    item = await db.get(BudgetItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    item.group_id = group_id
    item.supplier = supplier or None
    item.description = description or None
    item.priority = Priority(priority)
    item.planned_value = planned_value
    item.status = ItemStatus(status)
    await db.commit()
    ctx = await _budget_items_context(db)
    return templates.TemplateResponse(request, "partials/budget_items_rows.html", {
        **ctx,
    })


@router.delete("/previsto/{item_id}", response_class=HTMLResponse)
async def delete_budget_item_web(
    request: Request,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    item = await db.get(BudgetItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    await db.delete(item)
    await db.commit()
    ctx = await _budget_items_context(db)
    return templates.TemplateResponse(request, "partials/budget_items_rows.html", {
        **ctx,
    })


# --------------- Realizado ---------------

async def _transactions_context(
    db: AsyncSession,
    filter_group: str | None = None,
    filter_start: str | None = None,
    filter_end: str | None = None,
    filter_source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    groups = await _get_all_groups(db, include_inactive=False)
    group_map = {g.id: g.name for g in groups}

    stmt = select(Transaction).join(Group, Transaction.group_id == Group.id)
    count_stmt = select(func.count(Transaction.id)).join(Group, Transaction.group_id == Group.id)

    if filter_group:
        stmt = stmt.where(Transaction.group_id == uuid.UUID(filter_group))
        count_stmt = count_stmt.where(Transaction.group_id == uuid.UUID(filter_group))
    if filter_start:
        d = date.fromisoformat(filter_start)
        stmt = stmt.where(Transaction.transaction_date >= d)
        count_stmt = count_stmt.where(Transaction.transaction_date >= d)
    if filter_end:
        d = date.fromisoformat(filter_end)
        stmt = stmt.where(Transaction.transaction_date <= d)
        count_stmt = count_stmt.where(Transaction.transaction_date <= d)
    if filter_source:
        stmt = stmt.where(Transaction.source == filter_source)
        count_stmt = count_stmt.where(Transaction.source == filter_source)

    total_count = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    rows = list((await db.execute(stmt)).scalars().all())

    transactions = []
    for r in rows:
        transactions.append({
            "id": str(r.id),
            "group_id": str(r.group_id),
            "date_fmt": r.transaction_date.strftime("%d/%m/%Y") if r.transaction_date else "-",
            "date_iso": r.transaction_date.isoformat() if r.transaction_date else "",
            "group_name": group_map.get(r.group_id, "?"),
            "supplier": r.supplier,
            "description": r.description,
            "value_fmt": _fmt(r.value),
            "value_raw": str(r.value),
            "payment_method": r.payment_method.value if r.payment_method else None,
            "source": r.source.value if r.source else None,
            "input_type": r.input_type.value if r.input_type else None,
        })

    return {
        "groups": groups,
        "transactions": transactions,
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "filter_group": filter_group or "",
        "filter_start": filter_start or "",
        "filter_end": filter_end or "",
        "filter_source": filter_source or "",
    }


@router.get("/realizado", response_class=HTMLResponse)
async def realizado_page(
    request: Request,
    group_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    source: str | None = Query(None),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    ctx = await _transactions_context(db, group_id, start_date, end_date, source, offset)
    return templates.TemplateResponse(request, "realizado.html", {
        "active_page": "realizado",
        "today": date.today().isoformat(),
        **ctx,
    })


@router.post("/realizado", response_class=HTMLResponse)
async def create_transaction_web(
    request: Request,
    group_id: uuid.UUID = Form(...),
    transaction_date: date = Form(...),
    supplier: str | None = Form(None),
    value: float = Form(...),
    payment_method: str = Form(...),
    description: str | None = Form(None),
    observation: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    txn = Transaction(
        group_id=group_id,
        transaction_date=transaction_date,
        supplier=supplier or "",
        description=description or None,
        value=value,
        payment_method=PaymentMethod(payment_method),
        observation=observation or None,
        source=TransactionSource.manual,
    )
    db.add(txn)
    await db.commit()
    ctx = await _transactions_context(db)
    return templates.TemplateResponse(request, "partials/transactions_rows.html", {
        **ctx,
    })


@router.put("/realizado/{txn_id}", response_class=HTMLResponse)
async def update_transaction_web(
    request: Request,
    txn_id: uuid.UUID,
    group_id: uuid.UUID = Form(...),
    transaction_date: date = Form(...),
    supplier: str | None = Form(None),
    value: float = Form(...),
    payment_method: str = Form(...),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    txn.group_id = group_id
    txn.transaction_date = transaction_date
    txn.supplier = supplier or ""
    txn.description = description or None
    txn.value = value
    txn.payment_method = PaymentMethod(payment_method)
    await db.commit()
    ctx = await _transactions_context(db)
    return templates.TemplateResponse(request, "partials/transactions_rows.html", {
        **ctx,
    })


@router.delete("/realizado/{txn_id}", response_class=HTMLResponse)
async def delete_transaction_web(
    request: Request,
    txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _check_auth(request)
    txn = await db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    await db.delete(txn)
    await db.commit()
    ctx = await _transactions_context(db)
    return templates.TemplateResponse(request, "partials/transactions_rows.html", {
        **ctx,
    })
