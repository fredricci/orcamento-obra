"""Testes do middleware de API Key."""

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_api_key_missing_returns_401(noauth_client: AsyncClient):
    """Sem X-API-Key, /api/v1/* retorna 401."""
    response = await noauth_client.get("/api/v1/groups")
    assert response.status_code == 401
    assert "API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_invalid_returns_401(noauth_client: AsyncClient):
    """Com chave errada, /api/v1/* retorna 401."""
    response = await noauth_client.get("/api/v1/groups", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_valid_returns_200(client: AsyncClient):
    """Com chave correta, /api/v1/* retorna 200."""
    response = await client.get("/api/v1/groups")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_no_api_key(noauth_client: AsyncClient):
    """/health não exige API key."""
    response = await noauth_client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_key_budget_items(noauth_client: AsyncClient):
    """/api/v1/budget-items também exige API key."""
    response = await noauth_client.get("/api/v1/budget-items")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_transactions(noauth_client: AsyncClient):
    """/api/v1/transactions também exige API key."""
    response = await noauth_client.get("/api/v1/transactions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_dashboard(noauth_client: AsyncClient):
    """/api/v1/dashboard/summary também exige API key."""
    response = await noauth_client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401
