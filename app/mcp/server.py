"""MCP server com as 4 tools do orçamento de obra."""

from datetime import date
from decimal import Decimal
from typing import Any

import fastmcp
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.budget_item import BudgetItem
from app.models.group import Group
from app.models.transaction import InputType, PaymentMethod, Transaction, TransactionSource

VALID_PAYMENT_METHODS = [m.value for m in PaymentMethod]

# Engine compartilhado para o MCP (sem injeção de dependência do FastAPI)
_engine = None
_session_factory = None


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _session_factory


def _fmt(value) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):.2f}"


mcp = fastmcp.FastMCP("Orçamento de Obra")


@mcp.tool()
async def list_groups() -> list[dict]:
    """Retorna todos os grupos ativos com id e name."""
    _, factory = _get_engine()
    async with factory() as db:
        stmt = (
            select(Group)
            .where(Group.active.is_(True))
            .order_by(Group.sort_order.nullslast(), Group.name)
        )
        result = await db.execute(stmt)
        groups = result.scalars().all()
        return [{"id": str(g.id), "name": g.name} for g in groups]


@mcp.tool()
async def get_budget_overview() -> list[dict]:
    """Resumo previsto x realizado por grupo (todos os grupos ativos)."""
    _, factory = _get_engine()
    async with factory() as db:
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
            .where(Group.active.is_(True))
            .order_by(Group.sort_order.nullslast(), Group.name)
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


@mcp.tool()
async def create_transactions(items: list[dict]) -> dict:
    """
    Cria um ou mais lançamentos.

    Cada item deve ter:
    - transaction_date (YYYY-MM-DD, não pode ser no futuro)
    - group_name (nome exato do grupo, case-sensitive)
    - supplier (str)
    - description (str, opcional)
    - value (decimal positivo > 0)
    - payment_method: pix|credito_avista|credito_parcelado|debito|boleto|transferencia|dinheiro
    - observation (str, opcional)
    - input_type: image|pdf|audio|text|manual (opcional)
    """
    if not items:
        return {"error": "Lista de items não pode ser vazia"}

    _, factory = _get_engine()
    async with factory() as db:
        # Busca todos os grupos ativos
        stmt = select(Group).where(Group.active.is_(True))
        result = await db.execute(stmt)
        all_groups = result.scalars().all()
        group_by_name = {g.name: g for g in all_groups}
        valid_names = sorted(group_by_name.keys())

        created = []
        errors = []

        for i, item in enumerate(items):
            item_errors = []

            # Validar group_name
            group_name = item.get("group_name")
            if not group_name or group_name not in group_by_name:
                item_errors.append(
                    f"group_name '{group_name}' não encontrado. "
                    f"Grupos válidos: {valid_names}"
                )

            # Validar value
            try:
                value = Decimal(str(item.get("value", 0)))
                if value <= 0:
                    item_errors.append("value deve ser positivo e maior que 0")
            except Exception:
                item_errors.append("value deve ser um número decimal válido")
                value = None

            # Validar payment_method
            pm_str = item.get("payment_method")
            if pm_str not in VALID_PAYMENT_METHODS:
                item_errors.append(
                    f"payment_method '{pm_str}' inválido. "
                    f"Valores válidos: {VALID_PAYMENT_METHODS}"
                )
                pm = None
            else:
                pm = PaymentMethod(pm_str)

            # Validar transaction_date
            td_str = item.get("transaction_date")
            try:
                td = date.fromisoformat(str(td_str))
                if td > date.today():
                    item_errors.append("transaction_date não pode ser no futuro")
            except Exception:
                item_errors.append(f"transaction_date '{td_str}' inválida (use YYYY-MM-DD)")
                td = None

            # supplier
            supplier = item.get("supplier", "").strip()
            if not supplier:
                item_errors.append("supplier é obrigatório")

            if item_errors:
                errors.append({"item_index": i, "errors": item_errors, "item": item})
                continue

            # input_type opcional
            it_str = item.get("input_type")
            try:
                input_type = InputType(it_str) if it_str else None
            except ValueError:
                input_type = None

            group = group_by_name[group_name]
            txn = Transaction(
                group_id=group.id,
                transaction_date=td,
                supplier=supplier,
                description=item.get("description"),
                value=value,
                payment_method=pm,
                observation=item.get("observation"),
                source=TransactionSource.chat,
                input_type=input_type,
            )
            db.add(txn)
            created.append((txn, group_name))

        if errors:
            return {
                "error": "Alguns items têm erros de validação",
                "validation_errors": errors,
                "created_count": 0,
            }

        await db.commit()
        for txn, _ in created:
            await db.refresh(txn)

        # Calcular updated_balances por grupo afetado
        affected_group_names = {gn for _, gn in created}
        affected_groups = {name: group_by_name[name] for name in affected_group_names}

        updated_balances = []
        for gname, group in affected_groups.items():
            planned_q = select(func.coalesce(func.sum(BudgetItem.planned_value), 0)).where(
                BudgetItem.group_id == group.id
            )
            realized_q = select(func.coalesce(func.sum(Transaction.value), 0)).where(
                Transaction.group_id == group.id
            )
            planned = Decimal(str((await db.execute(planned_q)).scalar()))
            realized = Decimal(str((await db.execute(realized_q)).scalar()))
            updated_balances.append({
                "group_name": gname,
                "planned": _fmt(planned),
                "realized": _fmt(realized),
                "balance": _fmt(planned - realized),
            })

        created_items = []
        for txn, gname in created:
            created_items.append({
                "id": str(txn.id),
                "group_name": gname,
                "transaction_date": str(txn.transaction_date),
                "supplier": txn.supplier,
                "description": txn.description,
                "value": _fmt(txn.value),
                "payment_method": txn.payment_method.value if txn.payment_method else None,
                "observation": txn.observation,
                "input_type": txn.input_type.value if txn.input_type else None,
            })

        return {
            "created_count": len(created_items),
            "created": created_items,
            "updated_balances": updated_balances,
        }


@mcp.tool()
async def list_recent_transactions(limit: int = 10) -> list[dict]:
    """Retorna os lançamentos mais recentes."""
    _, factory = _get_engine()
    async with factory() as db:
        stmt = (
            select(Transaction, Group.name.label("group_name"))
            .join(Group, Transaction.group_id == Group.id)
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        result = []
        for txn, gname in rows:
            result.append({
                "id": str(txn.id),
                "group_name": gname,
                "transaction_date": str(txn.transaction_date),
                "supplier": txn.supplier,
                "description": txn.description,
                "value": _fmt(txn.value),
                "payment_method": txn.payment_method.value if txn.payment_method else None,
                "observation": txn.observation,
            })
        return result
