"""Middlewares da aplicação."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class MCPPathMiddleware(BaseHTTPMiddleware):
    """Reescreve /mcp/v1 → /mcp/v1/ internamente para evitar loop de redirect 307.

    O Claude.ai não segue redirects 307 em POST, então fazemos o rewrite
    de path antes do roteamento do FastAPI.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/mcp/v1":
            request.scope["path"] = "/mcp/v1/"
        return await call_next(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Exige X-API-Key ou Authorization: Bearer em rotas /api/v1/* e /mcp/v1/*."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/api/v1/") or path.startswith("/mcp/v1"):
            # Aceita X-API-Key header
            api_key = request.headers.get("X-API-Key")

            # Aceita Authorization: Bearer <token>
            if not api_key:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.lower().startswith("bearer "):
                    api_key = auth_header[7:].strip()

            if not api_key or api_key != settings.api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "API key ausente ou inválida"},
                    headers={"WWW-Authenticate": 'Bearer realm="Orcamento de Obra"'},
                )

        return await call_next(request)
