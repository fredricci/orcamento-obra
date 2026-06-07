# Orçamento de Obra

App pessoal de controle de orçamento de reforma residencial. Permite cadastrar grupos de despesa, definir orçamento previsto por grupo, registrar lançamentos (manualmente ou via Claude.ai com foto/áudio/texto) e acompanhar previsto x realizado no dashboard.

## Arquitetura

```mermaid
flowchart TD
    Browser --> Caddy
    Claude["Claude.ai (MCP)"] --> Caddy
    Caddy -->|":8000"| FastAPI
    FastAPI --> PostgreSQL
```

Stack: FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL 16 + Jinja2 + HTMX + Tailwind CSS.

## Como rodar local (Docker Compose)

### Pré-requisitos

- Docker 24+
- Docker Compose v2

### 1. Clone e configure

```bash
git clone <url-do-repo> orcamento-obra
cd orcamento-obra
cp .env.example .env
# Edite .env se necessário (os defaults funcionam para dev)
```

### 2. Suba os serviços

```bash
docker compose -f docker-compose.dev.yml up -d
```

Aguarde o healthcheck do Postgres passar (alguns segundos).

### 3. Rode as migrations + seed

```bash
docker compose -f docker-compose.dev.yml exec api alembic upgrade head
```

Isso cria as 3 tabelas e insere os 24 grupos de seed automaticamente.

### 4. Verifique

```bash
# Health check
curl http://localhost:8000/health

# Lista os 24 grupos
curl http://localhost:8000/api/v1/groups
```

Você deve ver os 24 grupos em JSON.

### 5. Acesse a documentação interativa

Abra http://localhost:8000/docs no browser.

---

## Rodar sem Docker (desenvolvimento direto)

```bash
# Crie e ative o venv
python3.12 -m venv venv
source venv/bin/activate

# Instale dependências
pip install -e ".[dev]" aiosqlite

# Suba apenas o Postgres via Docker
docker compose -f docker-compose.dev.yml up db -d

# Configure o .env
cp .env.example .env
# DATABASE_URL=postgresql+asyncpg://obra:obra@localhost:5432/orcamento_obra

# Rode migrations
alembic upgrade head

# Inicie a API
uvicorn app.main:app --reload
```

---

## Testes

```bash
source venv/bin/activate
pytest tests/ -v
```

Os testes usam SQLite em memória (sem necessidade de Postgres rodando).

---

## Exemplos de uso da API

### Listar grupos

```bash
curl http://localhost:8000/api/v1/groups
```

### Criar grupo

```bash
curl -X POST http://localhost:8000/api/v1/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "Novo Grupo", "sort_order": 25}'
```

### Atualizar grupo

```bash
curl -X PUT http://localhost:8000/api/v1/groups/<uuid> \
  -H "Content-Type: application/json" \
  -d '{"sort_order": 3}'
```

### Desativar grupo (soft delete)

```bash
curl -X DELETE http://localhost:8000/api/v1/groups/<uuid>
```

### Criar budget item (orçamento previsto)

```bash
curl -X POST http://localhost:8000/api/v1/budget-items \
  -H "Content-Type: application/json" \
  -d '{"group_id": "<uuid>", "description": "Box banho Luca", "priority": "alta", "planned_value": "200.00"}'
```

### Listar budget items (filtro por grupo)

```bash
curl http://localhost:8000/api/v1/budget-items?group_id=<uuid>
```

### Atualizar budget item

```bash
curl -X PUT http://localhost:8000/api/v1/budget-items/<uuid> \
  -H "Content-Type: application/json" \
  -d '{"planned_value": "350.00"}'
```

### Deletar budget item

```bash
curl -X DELETE http://localhost:8000/api/v1/budget-items/<uuid>
```

### Criar transactions (aceita array)

```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Content-Type: application/json" \
  -d '[
    {"group_id": "<uuid1>", "transaction_date": "2026-06-05", "supplier": "Leroy Merlin", "description": "Tomadas", "value": "350.00", "payment_method": "pix", "source": "manual"},
    {"group_id": "<uuid2>", "transaction_date": "2026-06-05", "supplier": "Casas Bahia", "description": "Eletrodomésticos", "value": "1200.00", "payment_method": "credito", "source": "manual"}
  ]'
```

### Listar transactions (com filtros)

```bash
# Todos
curl http://localhost:8000/api/v1/transactions

# Por grupo
curl http://localhost:8000/api/v1/transactions?group_id=<uuid>

# Por período
curl "http://localhost:8000/api/v1/transactions?start_date=2026-06-01&end_date=2026-06-30"

# Com limite
curl http://localhost:8000/api/v1/transactions?limit=10
```

### Atualizar transaction

```bash
curl -X PUT http://localhost:8000/api/v1/transactions/<uuid> \
  -H "Content-Type: application/json" \
  -d '{"value": "500.00"}'
```

### Deletar transaction

```bash
curl -X DELETE http://localhost:8000/api/v1/transactions/<uuid>
```

---

## Estrutura do repositório

```
orcamento-obra/
├── app/
│   ├── main.py          # FastAPI app
│   ├── config.py        # Configurações via env vars
│   ├── database.py      # Engine e sessão async
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── routers/         # Endpoints FastAPI
│   ├── services/        # Lógica de negócio
│   ├── mcp/             # MCP server (futuro)
│   ├── templates/       # Jinja2 templates (futuro)
│   └── static/          # Assets estáticos (futuro)
├── migrations/          # Alembic migrations
├── tests/               # Testes pytest
├── infra/               # Terraform (futuro)
├── deploy/              # Caddyfile, backup.sh (futuro)
├── Dockerfile
├── docker-compose.dev.yml
└── pyproject.toml
```

---

## Autenticação da API

Todas as rotas `/api/v1/*` exigem o header `X-API-Key`. Gere uma chave e configure no `.env`:

```bash
python scripts/bootstrap.py
```

O script imprime a chave gerada e as instruções completas.

Exemplo de uso:

```bash
# Com API key
curl -H "X-API-Key: sua-chave" http://localhost:8000/api/v1/groups

# Sem chave → 401
curl http://localhost:8000/api/v1/groups
```

---

## Como registrar o MCP server no Claude.ai

O MCP server fica disponível em `/mcp/v1` e expõe 4 tools:

| Tool | Descrição |
|------|-----------|
| `list_groups()` | Lista grupos ativos com id e name |
| `get_budget_overview()` | Resumo previsto x realizado por grupo |
| `create_transactions(items)` | Cria um ou mais lançamentos (aceita array) |
| `list_recent_transactions(limit)` | Lançamentos mais recentes |

### Registro no Claude.ai (interface web)

1. Acesse **claude.ai → Settings → Integrations → Add custom MCP**
2. Preencha:
   - **Name:** Orçamento de Obra
   - **URL:** `https://<seu-dominio>/mcp/v1`
   - **Header:** `X-API-Key: <sua-api-key>`

### Registro no Claude Desktop (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "orcamento-obra": {
      "url": "https://<seu-dominio>/mcp/v1",
      "headers": {
        "X-API-Key": "<sua-api-key>"
      }
    }
  }
}
```

Para desenvolvimento local: use `http://localhost:8000/mcp/v1` como URL.

### Exemplo de uso via MCP (create_transactions)

```json
{
  "items": [
    {
      "transaction_date": "2026-06-04",
      "group_name": "Acabamentos Elétricos",
      "supplier": "Leroy Merlin",
      "description": "Tomadas e interruptores",
      "value": "450.00",
      "payment_method": "credito_avista",
      "observation": null,
      "input_type": "image"
    }
  ]
}
```

`group_name` deve ser o nome exato (case-sensitive) de um grupo ativo. Se inválido, a resposta inclui a lista de grupos válidos.

---

## Segredos — geração inicial

```bash
# Gera API key aleatória com instruções completas
python scripts/bootstrap.py

# Gera senha do Postgres
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Coloque esses valores no `.env` do host (modo 600, nunca no git).

---

---

## Deploy em produção (AWS EC2)

### Visão geral

```
EC2 t4g.small (ARM, sa-east-1)
  └── Docker Compose
        ├── Caddy    (portas 80/443 — HTTPS automático)
        ├── FastAPI  (porta interna 8000)
        └── Postgres (porta interna 5432)

S3 bucket — backups diários via pg_dump + cron
```

### Pré-requisitos

- [Terraform >= 1.5](https://developer.hashicorp.com/terraform/downloads)
- AWS CLI configurado (`aws configure`) com permissões de EC2, S3 e IAM
- Key pair EC2 criada na região `sa-east-1`
- Domínio ou subdomínio apontando para o Elastic IP (ver passo de DNS abaixo)

---

### 1. Provisionar infraestrutura com Terraform

```bash
cd infra/

# Inicializar providers
terraform init

# Revisar o que será criado (sem aplicar)
terraform plan \
  -var="key_pair_name=minha-chave" \
  -var="my_ip=$(curl -s https://checkip.amazonaws.com)/32" \
  -var="domain=obra.duckdns.org"

# Criar recursos
terraform apply \
  -var="key_pair_name=minha-chave" \
  -var="my_ip=$(curl -s https://checkip.amazonaws.com)/32" \
  -var="domain=obra.duckdns.org"
```

Ao final, anote os outputs:
```
public_ip          = "54.X.X.X"
backup_bucket_name = "orcamento-obra-backup-123456789012"
ssh_command        = "ssh ubuntu@54.X.X.X"
```

Consulte `infra/README.md` para detalhes de cada variável.

---

### 2. Configurar DNS com DuckDNS (domínio gratuito)

1. Acesse [duckdns.org](https://www.duckdns.org) e crie um subdomínio (ex: `obraapp.duckdns.org`)
2. Aponte o subdomínio para o `public_ip` do Terraform output
3. Aguarde a propagação DNS (normalmente < 1 minuto para DuckDNS)
4. Verifique: `ping obraapp.duckdns.org` deve responder com o IP do EC2

---

### 3. Setup inicial no servidor

```bash
# SSH no EC2
ssh ubuntu@54.X.X.X

# Baixar e executar o script de bootstrap (como root)
sudo bash -c "
  apt-get update -qq
  apt-get install -y git
  git clone https://github.com/SEU_USUARIO/orcamento-obra.git /opt/orcamento-obra
  bash /opt/orcamento-obra/deploy/bootstrap.sh
"
```

O script instala Docker, Docker Compose e AWS CLI, e configura o cron de backup.

---

### 4. Criar o arquivo .env

```bash
# No servidor EC2
nano /opt/orcamento-obra/deploy/.env
chmod 600 /opt/orcamento-obra/deploy/.env
```

Conteúdo (substitua os valores):

```env
GHCR_OWNER=seu_usuario_github
DOMAIN=obraapp.duckdns.org

# Banco de dados
POSTGRES_DB=orcamento_obra
POSTGRES_USER=obra
POSTGRES_PASSWORD=<senha_aleatoria>

# Aplicação
API_KEY=<api_key_aleatoria>
BASIC_AUTH_USER=admin
BASIC_AUTH_PASSWORD=<senha_aleatoria>

# Backup S3
BUCKET_NAME=orcamento-obra-backup-123456789012
DB_CONTAINER=deploy-db-1
DB_NAME=orcamento_obra
DB_USER=obra
```

Para gerar senhas aleatórias:

```bash
openssl rand -hex 32
```

---

### 5. Subir os containers

```bash
cd /opt/orcamento-obra/deploy

# Primeira vez: build local (antes do CI/CD estar configurado)
docker compose pull || true
docker compose up -d

# Verificar logs
docker compose logs -f
```

---

### 6. Verificar HTTPS funcionando

```bash
# No seu computador local
curl -I https://obraapp.duckdns.org/health
# Deve retornar HTTP/2 200
```

O Caddy obtém o certificado TLS do Let's Encrypt automaticamente na primeira requisição. Aguarde ~30 segundos.

---

### 7. Configurar Secrets no GitHub (CI/CD)

No repositório GitHub, vá em **Settings → Secrets and variables → Actions** e adicione:

| Secret | Valor |
|--------|-------|
| `SSH_HOST` | IP público do EC2 (ex: `54.X.X.X`) |
| `SSH_USER` | `ubuntu` |
| `SSH_PRIVATE_KEY` | Conteúdo do arquivo `.pem` da key pair |

O `GITHUB_TOKEN` para push no GHCR é automático (não precisa configurar).

Após configurar os secrets, qualquer push na branch `main` fará:
1. Build da imagem Docker para `linux/arm64`
2. Push para `ghcr.io/SEU_USUARIO/orcamento-obra:latest`
3. SSH no EC2 → `docker compose pull && docker compose up -d`

---

### 8. Backup e restore

#### Testar backup manual

```bash
# No EC2
export BUCKET_NAME=orcamento-obra-backup-123456789012
export DB_CONTAINER=deploy-db-1
bash /opt/orcamento-obra/deploy/backup.sh
```

#### Listar backups disponíveis

```bash
aws s3 ls s3://orcamento-obra-backup-123456789012/
```

#### Restaurar backup de uma data específica

```bash
# ATENÇÃO: operação destrutiva — sobrescreve dados atuais
export BUCKET_NAME=orcamento-obra-backup-123456789012
export DB_CONTAINER=deploy-db-1
bash /opt/orcamento-obra/deploy/restore.sh 2026-06-07
```

O script pede confirmação antes de executar.

#### Cron de backup automático

O bootstrap.sh já configura o cron para rodar às 3am diariamente:

```bash
# Verificar cron instalado
crontab -l | grep backup

# Log do último backup
tail -20 /var/log/orcamento-backup.log
```

---

### Custos estimados (sa-east-1, após Free Tier)

| Recurso | Custo/mês |
|---------|-----------|
| EC2 t4g.small | ~US$ 12 |
| EBS 20 GB gp3 | ~US$ 2 |
| S3 backup (~500 MB) | ~US$ 0,10 |
| Tráfego saída | ~US$ 0–1 |
| **Total** | **~US$ 14–16** |
