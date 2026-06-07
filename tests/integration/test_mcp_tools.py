"""Testes end-to-end das tools MCP (chamando as funções diretamente com DB de teste)."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.group import Group
from app.models.budget_item import BudgetItem, Priority
from app.models.transaction import Transaction, PaymentMethod, TransactionSource

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def mcp_db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def mcp_session_factory(mcp_db_engine):
    return async_sessionmaker(mcp_db_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def group_eletricos(mcp_session_factory):
    """Cria um grupo de teste no DB."""
    async with mcp_session_factory() as db:
        group = Group(name="Acabamentos Elétricos", sort_order=1)
        db.add(group)
        await db.commit()
        await db.refresh(group)
        return group


@pytest_asyncio.fixture(scope="function")
async def group_hidraulica(mcp_session_factory):
    """Cria segundo grupo de teste."""
    async with mcp_session_factory() as db:
        group = Group(name="Hidráulica", sort_order=2)
        db.add(group)
        await db.commit()
        await db.refresh(group)
        return group


async def _run_with_factory(tool_fn, factory, *args, **kwargs):
    """Executa uma tool MCP injetando o session_factory de teste."""
    import app.mcp.server as srv
    original = srv._session_factory
    srv._session_factory = factory
    # Garantir que _engine não seja None (necessário para _get_engine)
    if srv._engine is None:
        srv._engine = object()  # placeholder
    try:
        return await tool_fn(*args, **kwargs)
    finally:
        srv._session_factory = original
        if srv._session_factory is original:
            srv._engine = None if original is None else srv._engine


@pytest.mark.asyncio
async def test_list_groups_empty(mcp_session_factory):
    """list_groups retorna lista vazia quando não há grupos."""
    import app.mcp.server as srv
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.list_groups()
        assert result == []
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_list_groups_with_data(mcp_session_factory, group_eletricos):
    """list_groups retorna grupos ativos."""
    import app.mcp.server as srv
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.list_groups()
        assert len(result) == 1
        assert result[0]["name"] == "Acabamentos Elétricos"
        assert "id" in result[0]
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_get_budget_overview(mcp_session_factory, group_eletricos):
    """get_budget_overview retorna resumo com planned/realized/balance."""
    import app.mcp.server as srv
    # Adiciona orçamento previsto
    async with mcp_session_factory() as db:
        item = BudgetItem(
            group_id=group_eletricos.id,
            description="Tomadas",
            priority=Priority.alta,
            planned_value=Decimal("1000.00"),
        )
        db.add(item)
        await db.commit()

    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.get_budget_overview()
        assert len(result) == 1
        row = result[0]
        assert row["group_name"] == "Acabamentos Elétricos"
        assert row["planned"] == "1000.00"
        assert row["realized"] == "0.00"
        assert row["balance"] == "1000.00"
        assert row["is_over_budget"] is False
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_create_transactions_invalid_group(mcp_session_factory, group_eletricos):
    """create_transactions rejeita group_name inválido com mensagem útil."""
    import app.mcp.server as srv
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.create_transactions([
            {
                "transaction_date": str(date.today()),
                "group_name": "Grupo Inexistente",
                "supplier": "Leroy Merlin",
                "description": "Tomadas",
                "value": "450.00",
                "payment_method": "pix",
            }
        ])
        assert "error" in result
        assert "validation_errors" in result
        err = result["validation_errors"][0]
        assert "Acabamentos Elétricos" in str(err["errors"])
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_create_transactions_single(mcp_session_factory, group_eletricos):
    """create_transactions cria lançamento único corretamente."""
    import app.mcp.server as srv
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.create_transactions([
            {
                "transaction_date": str(date.today()),
                "group_name": "Acabamentos Elétricos",
                "supplier": "Leroy Merlin",
                "description": "Tomadas e interruptores",
                "value": "450.00",
                "payment_method": "credito_avista",
                "observation": None,
                "input_type": "image",
            }
        ])
        assert result["created_count"] == 1
        assert result["created"][0]["group_name"] == "Acabamentos Elétricos"
        assert result["created"][0]["value"] == "450.00"
        assert len(result["updated_balances"]) == 1
        bal = result["updated_balances"][0]
        assert bal["realized"] == "450.00"
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_create_transactions_multi_group(mcp_session_factory, group_eletricos, group_hidraulica):
    """create_transactions aceita array com múltiplos grupos."""
    import app.mcp.server as srv
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.create_transactions([
            {
                "transaction_date": str(date.today()),
                "group_name": "Acabamentos Elétricos",
                "supplier": "Fornecedor A",
                "value": "100.00",
                "payment_method": "pix",
            },
            {
                "transaction_date": str(date.today()),
                "group_name": "Hidráulica",
                "supplier": "Fornecedor B",
                "value": "200.00",
                "payment_method": "debito",
            },
        ])
        assert result["created_count"] == 2
        group_names = {b["group_name"] for b in result["updated_balances"]}
        assert "Acabamentos Elétricos" in group_names
        assert "Hidráulica" in group_names
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_create_transactions_future_date(mcp_session_factory, group_eletricos):
    """create_transactions rejeita datas no futuro."""
    import app.mcp.server as srv
    from datetime import timedelta
    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        future = str(date.today() + timedelta(days=1))
        result = await srv.create_transactions([
            {
                "transaction_date": future,
                "group_name": "Acabamentos Elétricos",
                "supplier": "X",
                "value": "100.00",
                "payment_method": "pix",
            }
        ])
        assert "error" in result
        assert "validation_errors" in result
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine


@pytest.mark.asyncio
async def test_list_recent_transactions(mcp_session_factory, group_eletricos):
    """list_recent_transactions retorna lançamentos recentes."""
    import app.mcp.server as srv
    # Cria uma transaction diretamente
    async with mcp_session_factory() as db:
        txn = Transaction(
            group_id=group_eletricos.id,
            transaction_date=date.today(),
            supplier="Leroy Merlin",
            description="Fios",
            value=Decimal("300.00"),
            payment_method=PaymentMethod.pix,
            source=TransactionSource.manual,
        )
        db.add(txn)
        await db.commit()

    original_factory = srv._session_factory
    original_engine = srv._engine
    srv._session_factory = mcp_session_factory
    srv._engine = object()
    try:
        result = await srv.list_recent_transactions(limit=5)
        assert len(result) == 1
        assert result[0]["supplier"] == "Leroy Merlin"
        assert result[0]["value"] == "300.00"
        assert result[0]["group_name"] == "Acabamentos Elétricos"
    finally:
        srv._session_factory = original_factory
        srv._engine = original_engine
