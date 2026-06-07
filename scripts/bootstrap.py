#!/usr/bin/env python3
"""
Bootstrap script — gera uma API key aleatória e imprime instruções de configuração.

Uso:
    python scripts/bootstrap.py
"""

import secrets

api_key = secrets.token_urlsafe(32)

print("=" * 60)
print("ORÇAMENTO DE OBRA — Bootstrap")
print("=" * 60)
print()
print("API Key gerada:")
print(f"  {api_key}")
print()
print("Adicione no seu arquivo .env:")
print(f'  API_KEY={api_key}')
print()
print("=" * 60)
print("Como registrar o MCP server no Claude.ai")
print("=" * 60)
print()
print("1. Acesse claude.ai → Settings → Integrations → Add custom MCP")
print()
print("2. Preencha:")
print("   Name:    Orçamento de Obra")
print("   URL:     https://<seu-dominio>/mcp/v1")
print("   Header:  X-API-Key: <sua-api-key>")
print()
print("3. Ou use o conector via configuração JSON (claude_desktop_config.json):")
print()
print('   {')
print('     "mcpServers": {')
print('       "orcamento-obra": {')
print('         "url": "https://<seu-dominio>/mcp/v1",')
print('         "headers": {')
print(f'           "X-API-Key": "{api_key}"')
print('         }')
print('       }')
print('     }')
print('   }')
print()
print("4. Para teste local (sem TLS):")
print("   URL: http://localhost:8000/mcp/v1")
print()
print("Tools disponíveis via MCP:")
print("  - list_groups()")
print("  - get_budget_overview()")
print("  - create_transactions(items)")
print("  - list_recent_transactions(limit=10)")
print()
