"""Ponto de entrada da aplicação FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware import APIKeyMiddleware
from app.routers.groups import router as groups_router
from app.routers.budget_items import router as budget_items_router
from app.routers.transactions import router as transactions_router
from app.routers.dashboard import router as dashboard_router
from app.routers.web import router as web_router
from app.routers.oauth import router as oauth_router
from app.mcp.server import mcp

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app_started", env=settings.app_env, log_level=settings.log_level)
    yield


app = FastAPI(
    title="Orçamento de Obra",
    description="App de controle de orçamento de obra residencial",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# API Key middleware (protege /api/v1/*)
app.add_middleware(APIKeyMiddleware)

# Routers
app.include_router(groups_router)
app.include_router(budget_items_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)
app.include_router(web_router)
app.include_router(oauth_router)

# MCP server montado em /mcp/v1
mcp_app = mcp.http_app(path="/")
app.mount("/mcp/v1", mcp_app)


@app.get("/health", tags=["infra"])
async def health_check() -> JSONResponse:
    """Healthcheck básico — retorna 200 se o app está rodando."""
    return JSONResponse({"status": "ok", "env": settings.app_env})
