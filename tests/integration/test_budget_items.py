"""Testes de integração para o CRUD de budget items."""

import pytest
from httpx import AsyncClient

FAKE_UUID = "00000000-0000-0000-0000-000000000000"


async def _create_group(client: AsyncClient, name: str = "Vidraçaria") -> str:
    resp = await client.post("/api/v1/groups", json={"name": name})
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_budget_items_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/budget-items")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_budget_item(client: AsyncClient) -> None:
    group_id = await _create_group(client)
    payload = {
        "group_id": group_id,
        "description": "Box banho Luca",
        "priority": "alta",
        "planned_value": "200.00",
    }
    resp = await client.post("/api/v1/budget-items", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Box banho Luca"
    assert data["priority"] == "alta"
    assert data["planned_value"] == "200.00"
    assert data["group_id"] == group_id


@pytest.mark.asyncio
async def test_create_three_items_different_priorities(client: AsyncClient) -> None:
    """Critério de aceitação: 3 items no grupo Vidraçaria com prioridades diferentes."""
    group_id = await _create_group(client)
    items = [
        {"group_id": group_id, "description": "Box banho Luca", "priority": "alta", "planned_value": "200.00"},
        {"group_id": group_id, "description": "Box banho hóspedes", "priority": "media", "planned_value": "200.00"},
        {"group_id": group_id, "description": "Espelho hall social", "priority": "baixa", "planned_value": "500.00"},
    ]
    for item in items:
        resp = await client.post("/api/v1/budget-items", json=item)
        assert resp.status_code == 201

    # List filtered by group
    resp = await client.get(f"/api/v1/budget-items?group_id={group_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    priorities = {d["priority"] for d in data}
    assert priorities == {"alta", "media", "baixa"}


@pytest.mark.asyncio
async def test_create_budget_item_invalid_group(client: AsyncClient) -> None:
    payload = {
        "group_id": FAKE_UUID,
        "description": "Teste",
        "priority": "alta",
        "planned_value": "100.00",
    }
    resp = await client.post("/api/v1/budget-items", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_budget_item_zero_value(client: AsyncClient) -> None:
    group_id = await _create_group(client)
    payload = {
        "group_id": group_id,
        "description": "Teste",
        "priority": "alta",
        "planned_value": "0.00",
    }
    resp = await client.post("/api/v1/budget-items", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_budget_item(client: AsyncClient) -> None:
    group_id = await _create_group(client)
    create_resp = await client.post("/api/v1/budget-items", json={
        "group_id": group_id,
        "description": "Box",
        "priority": "alta",
        "planned_value": "200.00",
    })
    item_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/v1/budget-items/{item_id}", json={"planned_value": "350.00"})
    assert update_resp.status_code == 200
    assert update_resp.json()["planned_value"] == "350.00"


@pytest.mark.asyncio
async def test_delete_budget_item(client: AsyncClient) -> None:
    group_id = await _create_group(client)
    create_resp = await client.post("/api/v1/budget-items", json={
        "group_id": group_id,
        "description": "Temp",
        "priority": "baixa",
        "planned_value": "100.00",
    })
    item_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/budget-items/{item_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get(f"/api/v1/budget-items?group_id={group_id}")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_budget_item_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/budget-items/{FAKE_UUID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_by_group(client: AsyncClient) -> None:
    g1 = await _create_group(client, "Grupo A")
    g2 = await _create_group(client, "Grupo B")

    await client.post("/api/v1/budget-items", json={
        "group_id": g1, "description": "Item A", "priority": "alta", "planned_value": "100.00",
    })
    await client.post("/api/v1/budget-items", json={
        "group_id": g2, "description": "Item B", "priority": "media", "planned_value": "200.00",
    })

    resp = await client.get(f"/api/v1/budget-items?group_id={g1}")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["description"] == "Item A"
