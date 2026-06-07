"""OAuth 2.0 endpoints para integração com Claude.ai via MCP."""

import uuid
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import settings

router = APIRouter(tags=["oauth"])

# Armazenamento em memória (sem persistência)
_clients: dict[str, dict[str, Any]] = {}
_codes: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# OAuth Authorization Server Metadata (RFC 8414)
# ---------------------------------------------------------------------------

@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata() -> JSONResponse:
    base = settings.app_base_url
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
    })


# ---------------------------------------------------------------------------
# Dynamic Client Registration (RFC 7591)
# ---------------------------------------------------------------------------

@router.post("/oauth/register")
async def oauth_register(request: Request) -> JSONResponse:
    body = await request.json()
    client_id = str(uuid.uuid4())
    client_secret = str(uuid.uuid4())
    _clients[client_id] = {
        **body,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    return JSONResponse({
        "client_id": client_id,
        "client_secret": client_secret,
        **body,
    }, status_code=201)


# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------

def _auth_form_html(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
    error: str = "",
) -> str:
    error_block = f'<p class="text-red-600 text-sm mt-2">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Autorizar acesso</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
  <div class="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
    <h1 class="text-2xl font-bold text-gray-800 mb-2">Autorizar acesso ao Orçamento de Obra</h1>
    <p class="text-gray-600 mb-6">
      O Claude.ai quer acessar seu orçamento de obra para consultar grupos,
      lançamentos e dashboard. Confirme sua identidade para autorizar.
    </p>
    <form method="POST" action="/oauth/authorize">
      <input type="hidden" name="client_id" value="{client_id}"/>
      <input type="hidden" name="redirect_uri" value="{redirect_uri}"/>
      <input type="hidden" name="state" value="{state}"/>
      <input type="hidden" name="code_challenge" value="{code_challenge}"/>
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}"/>
      <label class="block text-sm font-medium text-gray-700 mb-1">Senha</label>
      <input
        type="password"
        name="password"
        placeholder="Digite sua senha"
        class="w-full border border-gray-300 rounded-lg px-4 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        autofocus
      />
      {error_block}
      <button
        type="submit"
        class="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition"
      >
        Autorizar
      </button>
    </form>
  </div>
</body>
</html>"""


@router.get("/oauth/authorize", response_class=HTMLResponse)
async def oauth_authorize_get(
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    response_type: str = "code",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
) -> HTMLResponse:
    return HTMLResponse(_auth_form_html(
        client_id, redirect_uri, state, code_challenge, code_challenge_method
    ))


@router.post("/oauth/authorize")
async def oauth_authorize_post(
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    state: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form("S256"),
    password: str = Form(""),
) -> Any:
    if password != settings.web_password:
        return HTMLResponse(
            _auth_form_html(
                client_id, redirect_uri, state,
                code_challenge, code_challenge_method,
                error="Senha incorreta. Tente novamente.",
            ),
            status_code=401,
        )

    code = str(uuid.uuid4())
    _codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }

    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={code}&state={state}"
    return RedirectResponse(location, status_code=302)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

@router.post("/oauth/token")
async def oauth_token(request: Request) -> JSONResponse:
    # Aceita tanto application/json quanto application/x-www-form-urlencoded
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    grant_type = body.get("grant_type")
    code = body.get("code", "")

    if grant_type != "authorization_code":
        return JSONResponse(
            {"error": "unsupported_grant_type"},
            status_code=400,
        )

    if code not in _codes:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Código inválido ou expirado"},
            status_code=400,
        )

    # Consome o code (one-time use)
    del _codes[code]

    return JSONResponse({
        "access_token": settings.api_key,
        "token_type": "bearer",
        "expires_in": 86400,
    })
