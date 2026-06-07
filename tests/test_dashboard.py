"""Testes dos endpoints de dashboard."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def seeded_client(client: AsyncClient):
    """Cria 3 grupos, 6 budget_items e 4 transactions para testes de dashboard."""
    # Grupo 1: Obra Civil — terá transactions dentro do budget
    g1 = await client.post("/api/v1/groups", json={"name": "Obra Civil", "sort_order": 1})
    g1_id = g1.json()["id"]

    # Grupo 2: Marcenaria — terá transactions acima do budget (over budget)
    g2 = await client.post("/api/v1/groups", json={"name": "Marcenaria", "sort_order": 2})
    g2_id = g2.json()["id"]

    # Grupo 3: Iluminação — sem transactions (deve retornar zeros)
    g3 = await client.post("/api/v1/groups", json={"name": "Iluminação", "sort_order": 3})
    g3_id = g3.json()["id"]

    # Budget items — 6 total across 3 groups, 3 priorities
    await client.post("/api/v1/budget-items", json={
        "group_id": g1_id, "description": "Demolição", "priority": "alta", "planned_value": 10000,
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g1_id, "description": "Alvenaria", "priority": "media", "planned_value": 15000,
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g2_id, "description": "Cozinha", "priority": "alta", "planned_value": 5000,
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g2_id, "description": "Quarto", "priority": "baixa", "planned_value": 3000,
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g3_id, "description": "Spots sala", "priority": "media", "planned_value": 2000,
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g3_id, "description": "Pendentes", "priority": "baixa", "planned_value": 1500,
    })

    # Transactions — 4 total (endpoint expects array)
    # Obra Civil: 8000 (within 25000 planned)
    await client.post("/api/v1/transactions", json=[
        {
            "group_id": g1_id, "supplier": "Empreiteiro", "description": "Demolição parcial",
            "value": 5000, "transaction_date": "2025-01-10", "payment_method": "pix",
        },
        {
            "group_id": g1_id, "supplier": "Empreiteiro", "description": "Alvenaria",
            "value": 3000, "transaction_date": "2025-01-15", "payment_method": "pix",
        },
    ])
    # Marcenaria: 10000 (over 8000 planned)
    await client.post("/api/v1/transactions", json=[
        {
            "group_id": g2_id, "supplier": "Marceneiro", "description": "Cozinha completa",
            "value": 7000, "transaction_date": "2025-02-01", "payment_method": "credito_avista",
        },
        {
            "group_id": g2_id, "supplier": "Marceneiro", "description": "Quarto",
            "value": 3000, "transaction_date": "2025-02-10", "payment_method": "credito_avista",
        },
    ])

    return client, g1_id, g2_id, g3_id


@pytest.mark.asyncio
async def test_summary(seeded_client):
    client, g1_id, g2_id, g3_id = seeded_client
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    # total_planned = 10000+15000+5000+3000+2000+1500 = 36500
    assert data["total_planned"] == "36500.00"
    # total_realized = 5000+3000+7000+3000 = 18000
    assert data["total_realized"] == "18000.00"
    # balance = planned - realized
    assert data["balance"] == "18500.00"
    assert data["balance"] == f"{36500 - 18000:.2f}"
    # percent
    assert abs(data["percent_executed"] - 18000 / 36500) < 0.01
    # Marcenaria is over budget (10000 realized > 8000 planned)
    assert "Marcenaria" in data["groups_over_budget"]
    assert "Obra Civil" not in data["groups_over_budget"]
    assert "Iluminação" not in data["groups_over_budget"]


@pytest.mark.asyncio
async def test_by_group(seeded_client):
    client, g1_id, g2_id, g3_id = seeded_client
    resp = await client.get("/api/v1/dashboard/by-group")
    assert resp.status_code == 200
    data = resp.json()

    by_name = {g["group_name"]: g for g in data}

    # All 3 active groups present
    assert len(by_name) == 3

    # Obra Civil: planned=25000, realized=8000
    oc = by_name["Obra Civil"]
    assert oc["planned"] == "25000.00"
    assert oc["realized"] == "8000.00"
    assert oc["balance"] == "17000.00"
    assert oc["is_over_budget"] is False

    # Marcenaria: planned=8000, realized=10000 — OVER BUDGET
    mc = by_name["Marcenaria"]
    assert mc["planned"] == "8000.00"
    assert mc["realized"] == "10000.00"
    assert mc["balance"] == "-2000.00"
    assert mc["is_over_budget"] is True
    assert mc["percent_executed"] > 1.0

    # Iluminação: no transactions — all zeros except planned
    il = by_name["Iluminação"]
    assert il["planned"] == "3500.00"
    assert il["realized"] == "0.00"
    assert il["balance"] == "3500.00"
    assert il["is_over_budget"] is False
    assert il["percent_executed"] == 0.0


@pytest.mark.asyncio
async def test_by_priority(seeded_client):
    client, *_ = seeded_client
    resp = await client.get("/api/v1/dashboard/by-priority")
    assert resp.status_code == 200
    data = resp.json()

    by_prio = {d["priority"]: d for d in data}

    # alta: 10000 + 5000 = 15000, 2 items
    assert by_prio["alta"]["planned"] == "15000.00"
    assert by_prio["alta"]["items_count"] == 2

    # media: 15000 + 2000 = 17000, 2 items
    assert by_prio["media"]["planned"] == "17000.00"
    assert by_prio["media"]["items_count"] == 2

    # baixa: 3000 + 1500 = 4500, 2 items
    assert by_prio["baixa"]["planned"] == "4500.00"
    assert by_prio["baixa"]["items_count"] == 2

    # Sum of all priorities = total planned
    total = sum(float(d["planned"]) for d in data)
    assert total == 36500.00


@pytest.mark.asyncio
async def test_empty_dashboard(client: AsyncClient):
    """Dashboard with no data should return zeros."""
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_planned"] == "0.00"
    assert data["total_realized"] == "0.00"
    assert data["balance"] == "0.00"
    assert data["groups_over_budget"] == []
