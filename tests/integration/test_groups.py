"""Testes de integração para o CRUD de grupos."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_groups_empty(client: AsyncClient) -> None:
    """GET /api/v1/groups retorna lista vazia quando não há grupos."""
    response = await client.get("/api/v1/groups")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_group(client: AsyncClient) -> None:
    """POST /api/v1/groups cria um grupo e retorna 201."""
    payload = {"name": "Obra Civil", "sort_order": 1}
    response = await client.post("/api/v1/groups", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Obra Civil"
    assert data["sort_order"] == 1
    assert data["active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_group_duplicate_returns_409(client: AsyncClient) -> None:
    """POST com nome duplicado retorna 409 Conflict."""
    payload = {"name": "Marcenaria"}
    await client.post("/api/v1/groups", json=payload)
    response = await client.post("/api/v1/groups", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_groups_after_create(client: AsyncClient) -> None:
    """GET após criações retorna todos os grupos ativos."""
    for nome in ["Vidraçaria", "Cortinas", "Decoração"]:
        await client.post("/api/v1/groups", json={"name": nome})

    response = await client.get("/api/v1/groups")
    assert response.status_code == 200
    names = [g["name"] for g in response.json()]
    assert "Vidraçaria" in names
    assert "Cortinas" in names
    assert "Decoração" in names


@pytest.mark.asyncio
async def test_update_group(client: AsyncClient) -> None:
    """PUT /api/v1/groups/{id} atualiza campos corretamente."""
    create_resp = await client.post("/api/v1/groups", json={"name": "Piso de Madeira", "sort_order": 10})
    group_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/v1/groups/{group_id}", json={"sort_order": 5})
    assert update_resp.status_code == 200
    assert update_resp.json()["sort_order"] == 5
    assert update_resp.json()["name"] == "Piso de Madeira"


@pytest.mark.asyncio
async def test_delete_group_soft(client: AsyncClient) -> None:
    """DELETE faz soft delete (active=false) e grupo some da listagem padrão."""
    create_resp = await client.post("/api/v1/groups", json={"name": "Chopeira"})
    group_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/groups/{group_id}")
    assert delete_resp.status_code == 204

    # Não aparece na listagem padrão
    list_resp = await client.get("/api/v1/groups")
    names = [g["name"] for g in list_resp.json()]
    assert "Chopeira" not in names

    # Aparece com include_inactive=true
    list_all_resp = await client.get("/api/v1/groups?include_inactive=true")
    names_all = [g["name"] for g in list_all_resp.json()]
    assert "Chopeira" in names_all


@pytest.mark.asyncio
async def test_delete_group_not_found(client: AsyncClient) -> None:
    """DELETE em grupo inexistente retorna 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/groups/{fake_id}")
    assert response.status_code == 404
