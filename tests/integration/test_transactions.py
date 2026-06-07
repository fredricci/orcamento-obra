"""Testes de integração para o CRUD de transactions."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

FAKE_UUID = "00000000-0000-0000-0000-000000000000"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


async def _create_group(client: AsyncClient, name: str = "Obra Civil") -> str:
    resp = await client.post("/api/v1/groups", json={"name": name})
    return resp.json()["id"]


def _txn_payload(group_id: str, **overrides) -> dict:
    base = {
        "group_id": group_id,
        "transaction_date": TODAY,
        "supplier": "Leroy Merlin",
        "description": "Tomadas",
        "value": "350.00",
        "payment_method": "pix",
        "source": "manual",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_list_transactions_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/transactions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_single_transaction(client: AsyncClient) -> None:
    gid = await _create_group(client)
    payload = [_txn_payload(gid)]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["supplier"] == "Leroy Merlin"
    assert data[0]["value"] == "350.00"
    assert data[0]["payment_method"] == "pix"


@pytest.mark.asyncio
async def test_create_array_multi_group(client: AsyncClient) -> None:
    """Critério de aceitação: POST com array de 2 items em grupos diferentes."""
    g1 = await _create_group(client, "Marcenaria")
    g2 = await _create_group(client, "Iluminação Técnica")
    payload = [
        _txn_payload(g1, supplier="Madeireira Silva", value="1200.00", payment_method="credito_avista"),
        _txn_payload(g2, supplier="Elétrica Central", value="450.00", payment_method="debito"),
    ]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    suppliers = {d["supplier"] for d in data}
    assert suppliers == {"Madeireira Silva", "Elétrica Central"}


@pytest.mark.asyncio
async def test_create_transaction_value_zero(client: AsyncClient) -> None:
    gid = await _create_group(client)
    payload = [_txn_payload(gid, value="0.00")]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_transaction_future_date(client: AsyncClient) -> None:
    gid = await _create_group(client)
    payload = [_txn_payload(gid, transaction_date=TOMORROW)]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_transaction_invalid_group(client: AsyncClient) -> None:
    payload = [_txn_payload(FAKE_UUID)]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_transaction_invalid_payment_method(client: AsyncClient) -> None:
    gid = await _create_group(client)
    payload = [_txn_payload(gid, payment_method="bitcoin")]
    resp = await client.post("/api/v1/transactions", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_group(client: AsyncClient) -> None:
    g1 = await _create_group(client, "Grupo X")
    g2 = await _create_group(client, "Grupo Y")
    await client.post("/api/v1/transactions", json=[_txn_payload(g1)])
    await client.post("/api/v1/transactions", json=[_txn_payload(g2, supplier="Outro")])

    resp = await client.get(f"/api/v1/transactions?group_id={g1}")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["group_id"] == g1


@pytest.mark.asyncio
async def test_filter_by_date_range(client: AsyncClient) -> None:
    gid = await _create_group(client)
    await client.post("/api/v1/transactions", json=[_txn_payload(gid, transaction_date=TODAY)])
    await client.post("/api/v1/transactions", json=[_txn_payload(gid, transaction_date=YESTERDAY, supplier="Ontem")])

    # Only yesterday
    resp = await client.get(f"/api/v1/transactions?start_date={YESTERDAY}&end_date={YESTERDAY}")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["supplier"] == "Ontem"


@pytest.mark.asyncio
async def test_filter_limit(client: AsyncClient) -> None:
    gid = await _create_group(client)
    for i in range(5):
        await client.post("/api/v1/transactions", json=[_txn_payload(gid, supplier=f"S{i}")])

    resp = await client.get("/api/v1/transactions?limit=2")
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_transaction(client: AsyncClient) -> None:
    gid = await _create_group(client)
    create_resp = await client.post("/api/v1/transactions", json=[_txn_payload(gid)])
    txn_id = create_resp.json()[0]["id"]

    update_resp = await client.put(f"/api/v1/transactions/{txn_id}", json={"value": "500.00"})
    assert update_resp.status_code == 200
    assert update_resp.json()["value"] == "500.00"


@pytest.mark.asyncio
async def test_delete_transaction(client: AsyncClient) -> None:
    gid = await _create_group(client)
    create_resp = await client.post("/api/v1/transactions", json=[_txn_payload(gid)])
    txn_id = create_resp.json()[0]["id"]

    del_resp = await client.delete(f"/api/v1/transactions/{txn_id}")
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/v1/transactions")
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_transaction_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/transactions/{FAKE_UUID}")
    assert resp.status_code == 404
