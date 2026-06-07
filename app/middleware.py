"""Middleware de autenticação por API Key para rotas /api/v1/*."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Exige X-API-Key header em todas as rotas /api/v1/*."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/") or path.startswith("/mcp/v1/"):
            # Aceita X-API-Key ou Authorization: Bearer <token>
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.lower().startswith("bearer "):
                    api_key = auth_header[7:]
            if not api_key or api_key != settings.api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "API key ausente ou inválida"},
                )
        response = await call_next(request)
        return response
