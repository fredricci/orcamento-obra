# Especificação — App de Controle de Orçamento de Obra

> Projeto novo, sem reaproveitamento de código de outros projetos. Construir do zero.

## 1. Visão Geral

Aplicação web pessoal para controlar o orçamento de uma obra residencial (reforma de apartamento). Permite cadastrar grupos de despesa, definir o orçamento previsto por grupo, registrar lançamentos realizados via integração com Claude (chat), e visualizar comparativo previsto x realizado em dashboard.

**Usuário único** (eu mesmo). Sem multi-tenancy, sem cadastro público.

## 2. Stack Tecnológica

- **Backend:** Python 3.12, FastAPI
- **Banco:** PostgreSQL 16
- **ORM:** SQLAlchemy 2.x + Alembic (migrations)
- **Frontend:** Jinja2 templates + HTMX + Tailwind CSS (server-rendered, sem SPA)
- **Containerização:** Docker (multi-stage build) + Docker Compose
- **HTTPS / reverse proxy:** Caddy (HTTPS automático via Let's Encrypt)
- **Registry:** GitHub Container Registry (GHCR)
- **Deploy:** AWS EC2 (single host) — ver seção 10 pra detalhe
- **Region:** `sa-east-1` (São Paulo)
- **CI/CD:** GitHub Actions
- **Linting/Format:** ruff + black
- **Tests:** pytest + httpx + pytest-asyncio
- **Logs:** structlog (JSON) → docker logs → logrotate

## 3. Arquitetura

```
┌──────────────────────┐      HTTPS       ┌──────────────────────────────┐
│ Browser (eu)         │ ───────────────► │   EC2 t4g.small (sa-east-1)  │
│ Telas de gestão      │                  │                              │
└──────────────────────┘                  │   ┌─────────────────────┐    │
                                          │   │ Caddy (porta 443)   │    │
┌──────────────────────┐      MCP/HTTPS   │   │ HTTPS + reverse     │    │
│ Claude.ai (chat)     │ ───────────────► │   │ proxy               │    │
│ via MCP connector    │                  │   └──────────┬──────────┘    │
│ customizado          │                  │              │               │
└──────────────────────┘                  │   ┌──────────▼──────────┐    │
                                          │   │ FastAPI (porta 8000)│    │
                                          │   │  - Web routes       │    │
                                          │   │  - REST API         │    │
                                          │   │  - MCP server       │    │
                                          │   └──────────┬──────────┘    │
                                          │              │               │
                                          │   ┌──────────▼──────────┐    │
                                          │   │ PostgreSQL 16       │    │
                                          │   │ (mesmo host)        │    │
                                          │   └─────────────────────┘    │
                                          │                              │
                                          │   Backups: cron pg_dump → S3 │
                                          └──────────────────────────────┘
```

Tudo no mesmo EC2 via Docker Compose. Caddy é o único exposto na 443.

## 4. Modelo de Dados

### Tabela `groups`

| Campo        | Tipo        | Notas                                    |
|--------------|-------------|------------------------------------------|
| id           | UUID PK     |                                          |
| name         | VARCHAR(80) | UNIQUE, NOT NULL                         |
| sort_order   | INTEGER     | Pra ordenação na UI                      |
| active       | BOOLEAN     | Default `true`, permite desativar grupo  |
| created_at   | TIMESTAMP   |                                          |
| updated_at   | TIMESTAMP   |                                          |

**Seed inicial** (executar via migration ou script de bootstrap) — 24 grupos:

```
Obra Civil, Limpeza, Ar Condicionado, Iluminação Técnica, Iluminação Decorativa,
Acabamentos Elétricos, Louças e Metais, Piso Porcelanato, Revestimento,
Piso de Madeira, Marcenaria, Aquecedor a Gás, Fechamento Varanda, Vidraçaria,
Acessórios, Churrasqueira, Automação, Chopeira, Eletrodomésticos, Mobílias,
Cortinas, Decoração, Varal, Fechadura Digital
```

### Tabela `budget_items` (orçamento previsto)

**Múltiplas linhas por grupo são esperadas e suportadas.** Cada linha representa um sub-item planejado, com fornecedor, descrição, prioridade e valor próprios. Não há constraint UNIQUE no `group_id` — propositadamente.

Exemplo: o grupo "Vidraçaria" pode ter 3 linhas:

| group_id     | supplier  | description           | priority | planned_value |
|--------------|-----------|-----------------------|----------|---------------|
| vidracaria   | (vazio)   | Box banho Luca        | alta     | 200.00        |
| vidracaria   | (vazio)   | Box banho hóspedes    | media    | 200.00        |
| vidracaria   | (vazio)   | Espelho do hall social| baixa    | 500.00        |

| Campo         | Tipo          | Notas                                          |
|---------------|---------------|------------------------------------------------|
| id            | UUID PK       |                                                |
| group_id      | UUID FK       | → groups.id                                    |
| supplier      | VARCHAR(120)  | Empresa/fornecedor previsto (nullable)         |
| description   | TEXT          |                                                |
| priority      | ENUM          | 'alta' \| 'media' \| 'baixa'                   |
| planned_value | NUMERIC(12,2) | NOT NULL                                       |
| created_at    | TIMESTAMP     |                                                |
| updated_at    | TIMESTAMP     |                                                |

### Tabela `transactions` (realizado)

| Campo            | Tipo          | Notas                                                  |
|------------------|---------------|--------------------------------------------------------|
| id               | UUID PK       |                                                        |
| group_id         | UUID FK       | → groups.id                                            |
| transaction_date | DATE          | Data da compra/pagamento                               |
| supplier         | VARCHAR(120)  | NOT NULL                                               |
| description      | TEXT          | Item(s) comprado(s)                                    |
| value            | NUMERIC(12,2) | NOT NULL                                               |
| payment_method   | ENUM          | 'pix','credito','debito','boleto','transferencia','dinheiro' |
| observation      | TEXT          | Nullable                                               |
| source           | ENUM          | 'chat' \| 'manual' (origem do lançamento)              |
| input_type       | ENUM          | 'image','pdf','audio','text','manual' (nullable)       |
| receipt_ref      | VARCHAR(255)  | Nullable. Pra futuro upload de comprovante (S3 key)    |
| created_at       | TIMESTAMP     |                                                        |
| updated_at       | TIMESTAMP     |                                                        |

### Indexes

- `transactions(group_id, transaction_date DESC)`
- `transactions(transaction_date DESC)`
- `budget_items(group_id)`

## 5. Endpoints da API REST

Todas as respostas em JSON. Datas em ISO 8601. Valores monetários em string decimal (`"1245.50"`).

### Grupos
- `GET /api/v1/groups`
- `POST /api/v1/groups`
- `PUT /api/v1/groups/{id}`
- `DELETE /api/v1/groups/{id}` — soft delete (`active=false`)

### Orçamento Previsto
- `GET /api/v1/budget-items` (filtro: `?group_id=`)
- `POST /api/v1/budget-items`
- `PUT /api/v1/budget-items/{id}`
- `DELETE /api/v1/budget-items/{id}`

### Lançamentos Realizados
- `GET /api/v1/transactions` (filtros: `?group_id=`, `?start_date=`, `?end_date=`, `?limit=`)
- `POST /api/v1/transactions` (aceita array pra multi-grupo)
- `PUT /api/v1/transactions/{id}`
- `DELETE /api/v1/transactions/{id}`

### Dashboard
- `GET /api/v1/dashboard/summary`
  ```json
  {
    "total_planned": "85000.00",
    "total_realized": "32450.00",
    "balance": "52550.00",
    "percent_executed": 0.382,
    "groups_over_budget": ["Acabamentos Elétricos"]
  }
  ```
- `GET /api/v1/dashboard/by-group`
  ```json
  [
    {
      "group_id": "...",
      "group_name": "Acabamentos Elétricos",
      "planned": "12000.00",
      "realized": "12850.00",
      "balance": "-850.00",
      "percent_executed": 1.071,
      "is_over_budget": true
    }
  ]
  ```
- `GET /api/v1/dashboard/by-priority` — agregação **apenas do previsto** por prioridade. Não compara com realizado (decisão consciente: prioridade só existe em `budget_items`, não em `transactions`).
  ```json
  [
    { "priority": "alta",  "planned": "35000.00", "items_count": 12 },
    { "priority": "media", "planned": "28000.00", "items_count": 8  },
    { "priority": "baixa", "planned": "22000.00", "items_count": 6  }
  ]
  ```

### Auth
- API REST e MCP: header `X-API-Key: <key>` (chave única gerada no bootstrap, armazenada no `.env` do host)
- UI web: basic auth via Caddy ou middleware FastAPI (usuário/senha em env var; um usuário só)

## 6. Integração MCP (chat com Claude)

Expor MCP server em `/mcp/v1` seguindo o protocolo Model Context Protocol. Registrar como custom connector no Claude.ai.

### Modalidades de input suportadas no chat

O usuário pode iniciar um lançamento de **3 formas distintas**, e o backend MCP não precisa diferenciar — o Claude faz a extração de cada modalidade nativamente e chama as mesmas tools:

1. **Foto, PDF ou imagem de NF/cupom/comprovante** — Claude usa visão nativa pra extrair data, fornecedor, itens e valor
2. **Mensagem de áudio** — Claude transcreve nativamente e extrai os campos da fala (ex: "paguei 350 reais no Leroy hoje, tomadas e interruptores, cartão de crédito")
3. **Mensagem de texto livre** — Claude parseia direto (ex: "lança 1.200 da Casas Bahia em eletrodomésticos, pix de ontem")

Pra **qualquer** modalidade:
- Se faltar info essencial (valor, fornecedor, data, grupo), Claude **pergunta** antes de propor
- Se a info estiver ambígua (ex: fornecedor pode ser de 2 grupos diferentes), Claude esclarece antes de propor
- Sempre passa pela proposta + confirmação antes de gravar
- O campo `input_type` na transaction registra de qual modalidade veio (útil pra auditoria depois)

### Ferramentas MCP expostas

#### `list_groups()`
Retorna grupos ativos.

#### `get_budget_overview()`
Resumo previsto x realizado por grupo. Útil pra responder saldo sem múltiplas chamadas.

#### `create_transactions(items)`
Cria um ou mais lançamentos multi-grupo. **Só chamada após confirmação explícita do usuário.**

**Args:**
```json
{
  "items": [
    {
      "transaction_date": "2026-06-04",
      "group_name": "Acabamentos Elétricos",
      "supplier": "Leroy Merlin",
      "description": "Tomadas e interruptores",
      "value": "450.00",
      "payment_method": "credito",
      "observation": null,
      "input_type": "image"
    }
  ]
}
```

**Returns:**
```json
{
  "created": [{ "id": "...", "group_name": "...", "value": "..." }],
  "updated_balances": [
    {
      "group_name": "Acabamentos Elétricos",
      "planned": "12000.00",
      "realized": "8650.00",
      "balance": "3350.00",
      "percent_executed": 0.721
    }
  ]
}
```

Validações na entrada:
- `group_name` deve bater EXATAMENTE com um nome em `groups.name` (case-sensitive). Se não bater, retornar erro com a lista de grupos válidos.
- `value` decimal positivo > 0
- `payment_method` ∈ enum válido
- `transaction_date` não no futuro
- `input_type` ∈ {`image`,`pdf`,`audio`,`text`,`manual`} (opcional)

#### `list_recent_transactions(limit=10)`
Lança recentes pra contexto ("quanto gastei essa semana").

### Fluxo conversacional canônico

1. Eu mando foto/PDF/áudio/texto descrevendo a compra
2. Claude extrai os dados (visão/transcrição/parsing) e chama `list_groups()` pra ter a lista canônica
3. Claude classifica cada item; se a NF tem itens de grupos diferentes, divide em N linhas
4. Claude me mostra a proposta em texto e pergunta "confirma?"
5. Eu confirmo (ou corrijo)
6. Após confirmação, Claude chama `create_transactions(items)` com o `input_type` apropriado
7. Claude me devolve os saldos atualizados

**Regra crítica:** o MCP server NÃO deve ter nenhuma ferramenta que pule a confirmação. Não criar `create_transactions_auto` ou similar.

### Autenticação do MCP

API key estática no header. Gerada no bootstrap, armazenada em `.env` do host.

## 7. Telas (UI Web)

Todas em português, BRL, datas dd/mm/aaaa. Tailwind, design limpo.

### `/` — Dashboard
- Card no topo: Total Previsto, Total Realizado, Saldo, % Executado
- Tabela por grupo: Grupo | Previsto | Realizado | Saldo | % Executado
- Saldo negativo em vermelho
- Gráfico de barras horizontal (previsto vs realizado)
- **Seção "Previsto por Prioridade"**: 3 cards (Alta / Média / Baixa) mostrando o total previsto e a quantidade de itens em cada nível. Útil pra decisões de prioridade quando o orçamento aperta. Sem comparação com realizado.

### `/grupos` — Gestão de Grupos
- Listagem ordenada
- Adicionar / editar / desativar
- Botão pra reordenar (ou input numérico `sort_order`)

### `/previsto` — Orçamento Previsto
- Filtro por grupo e por prioridade
- Tabela: Grupo | Fornecedor | Descrição | Prioridade | Valor Previsto | Ações
- **Múltiplas linhas do mesmo grupo são esperadas** (ex: 3 linhas de Vidraçaria com prioridades diferentes — ver exemplo na §4)
- Soma total no rodapé (respeitando os filtros aplicados)
- Adicionar / editar / deletar

### `/realizado` — Lançamentos Realizados
- Filtros: grupo, período, origem (chat/manual), tipo de input
- Tabela: Data | Grupo | Fornecedor | Descrição | Valor | Forma Pgto | Origem | Tipo Input | Ações
- Botão "Lançamento manual"
- Default sort: data desc

## 8. Fluxos Principais

### Fluxo 1: Setup inicial
1. Provisionar EC2 + EBS + Security Group (Terraform — seção 10)
2. SSH no host, clonar repo, criar `.env`, rodar `docker compose up -d`
3. Acessar via HTTPS pelo domínio
4. Grupos já vêm via seed; cadastrar orçamento em `/previsto`
5. Gerar API key, registrar MCP server no Claude.ai

### Fluxo 2: Lançamento via chat (caminho feliz, multi-modal)
1. Abro chat no Claude.ai (conector já registrado)
2. Anexo foto/áudio OU descrevo por texto
3. Claude extrai/transcreve/parseia → classifica → propõe → pergunta
4. Confirmo
5. `create_transactions` é chamada com `input_type` correto
6. Claude me devolve saldo atualizado

### Fluxo 3: Ajuste manual via web
1. `/realizado` → filtro → editar/deletar

## 9. Requisitos Funcionais Detalhados

- [RF01] Cadastrar grupos com nome único
- [RF02] Cadastrar múltiplos itens de orçamento previsto por grupo
- [RF03] Cadastrar lançamento realizado (manualmente ou via chat — imagem, PDF, áudio, texto)
- [RF04] Listar lançamentos com filtros por grupo, data, origem, tipo de input
- [RF05] Editar e deletar grupos, itens previstos e lançamentos
- [RF06] Calcular dashboard com totais previstos, realizados, saldo e % executado
- [RF07] Sinalizar grupos que estouraram o orçamento
- [RF08] Expor MCP server pra integração com Claude.ai
- [RF09] Aceitar lançamentos multi-grupo numa única chamada
- [RF10] Validar nome de grupo contra lista canônica antes de gravar
- [RF11] Registrar origem (`source`) e modalidade (`input_type`) de cada lançamento
- [RF12] Autenticar API e UI
- [RF13] Suportar múltiplos itens previstos por grupo, cada um com fornecedor, descrição, prioridade e valor independentes
- [RF14] Dashboard agrega valor previsto por prioridade (alta/média/baixa), sem comparar com realizado

## 10. Infraestrutura AWS — Opção A: Low-Cost (recomendada)

### Componentes
- **EC2 t4g.small** (ARM Graviton, 2 vCPU, 2 GB RAM) — único host
- **EBS gp3 20 GB** — disco do EC2
- **Elastic IP** — IP fixo pra DNS
- **S3 bucket** (Standard-IA + Lifecycle pra Glacier após 30d) — backups de Postgres via cron `pg_dump`
- **Security Group** — entrada só 22 (SSH, restrito ao meu IP) e 443 (HTTPS público)
- **IAM role** — pra EC2 conseguir escrever no S3 (backup)

### Software no host (via Docker Compose)
- **FastAPI** (container, porta interna 8000)
- **PostgreSQL 16** (container, porta interna 5432, volume EBS)
- **Caddy** (container, portas 80/443) — terminação TLS automática via Let's Encrypt

### DNS / Domínio
- Domínio próprio em Registro.br (.com.br, ~R$40/ano) **ou** subdomínio grátis via Duck DNS (`obraapp.duckdns.org`)
- Apontar A record pro Elastic IP

### Backup
- `cron` no host: `pg_dump` diário → comprime → `aws s3 cp` pro bucket
- Retention: 7 dias em S3-IA + 90 dias em Glacier
- Script de restore documentado no README

### Logs
- `docker logs` → arquivo via driver `json-file` com rotação (max 10 MB, 5 arquivos)
- Sem CloudWatch (zero custo)

### Secrets
- `.env` no host, modo 600, fora do git
- Documentar geração inicial das chaves (API_KEY, DB_PASSWORD, BASIC_AUTH) no README

### Custos estimados
- **Free Tier (primeiros 12 meses, se ainda não consumido):** ~US$ 0
- **Após Free Tier:**
  - EC2 t4g.small: ~US$ 12/mês (sa-east-1, on-demand)
  - EBS 20 GB gp3: ~US$ 2/mês
  - S3 backup (~500 MB): ~US$ 0.10/mês
  - Tráfego saída: ~US$ 0–1/mês (uso pessoal)
  - **Total: ~US$ 14–16/mês**

> Se quiser baixar mais ainda: **t4g.nano** (~US$3/mês) funciona pra começar, mas pode ficar lento conforme o banco cresce. **t4g.small** é o sweet spot.

### Provisionamento
**Terraform** em pasta `infra/`. Arquivos:
- `main.tf` — EC2, EBS, EIP, SG, IAM role
- `s3.tf` — bucket de backup com lifecycle
- `outputs.tf` — IP público, instance ID
- `variables.tf` — region, key pair, AMI ID

### Trade-offs aceitos
- **SPOF**: tudo num host só. Aceito pra uso pessoal.
- **Sem auto-scale**: irrelevante (1 usuário).
- **Sem multi-AZ no banco**: backups diários em S3 cobrem o pior caso.
- **Deploy via SSH** (não push-button): GitHub Actions SSH-a no host, faz `docker compose pull && docker compose up -d`.

## 10b. Infraestrutura AWS — Opção B: Managed Services (alternativa)

Se um dia escalar ou quiser menos manutenção operacional, migrar pra:
- **App Runner** (auto deploy, autoscale, HTTPS gerenciado) — ~US$10-20/mês
- **RDS PostgreSQL** (backups gerenciados, multi-AZ opcional) — ~US$15/mês
- **ECR** (registry) — ~US$1/mês
- **Secrets Manager**, **CloudWatch** — ~US$2/mês

**Total Opção B: ~US$28-38/mês**. Não recomendado pra começar.

## 11. CI/CD (GitHub Actions)

### Workflow `ci.yml` (em push e PR)
- Checkout, setup Python 3.12
- Instalar deps
- `ruff check` + `black --check`
- `pytest` (com Postgres em container via service container)

### Workflow `deploy.yml` (em push na `main`, após CI passar)
- Build Docker image
- Push pra **GHCR** (`ghcr.io/<owner>/orcamento-obra:latest` + tag por commit SHA)
- SSH no EC2:
  - `docker compose pull`
  - `docker compose up -d`
  - `docker image prune -f`

### Secrets necessários no GitHub
- `SSH_PRIVATE_KEY` — chave pra SSH no EC2
- `SSH_HOST` — IP/DNS do EC2
- `SSH_USER` — usuário (ex: `ubuntu`)
- `GHCR_TOKEN` — pra push no registry (ou usar `GITHUB_TOKEN` que já tem permissão)

## 12. Estrutura do Repositório

```
orcamento-obra/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py
│   ├── database.py
│   ├── models/              # SQLAlchemy
│   ├── schemas/             # Pydantic
│   ├── routers/
│   │   ├── groups.py
│   │   ├── budgets.py
│   │   ├── transactions.py
│   │   ├── dashboard.py
│   │   └── web.py           # Jinja routes
│   ├── mcp/
│   │   ├── server.py
│   │   └── tools.py
│   ├── templates/           # Jinja2
│   ├── static/              # CSS, JS, Tailwind build
│   └── services/            # lógica de negócio
├── migrations/              # Alembic
├── tests/
│   ├── unit/
│   └── integration/
├── infra/                   # Terraform (EC2, EBS, EIP, SG, S3)
├── deploy/
│   ├── docker-compose.yml   # rodar em prod no EC2
│   ├── Caddyfile            # config do Caddy
│   └── backup.sh            # script de pg_dump → S3
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── Dockerfile               # multi-stage
├── docker-compose.dev.yml   # pra dev local
├── pyproject.toml
├── README.md
└── .env.example
```

## 13. Segurança

- HTTPS obrigatório (Caddy + Let's Encrypt automático)
- API Key em header pra REST e MCP, rotacionável editando `.env` e reiniciando container
- Senha do Postgres random no setup, armazenada em `.env`
- `.env` no `.gitignore`, modo 600 no host
- SSH apenas via key pair, sem senha; SG restringe porta 22 ao meu IP
- Logs não devem registrar valores sensíveis
- Dependências auditadas com `pip-audit` no CI

## 14. Requisitos Não-Funcionais

- **Performance:** P95 < 300ms (uso pessoal, baixíssimo volume)
- **Disponibilidade:** sem SLA formal; downtime ocasional aceito. Backups diários.
- **Observabilidade:** logs estruturados em JSON via structlog; healthcheck `/health` (200 se DB conectado)
- **i18n:** PT-BR somente
- **Acessibilidade:** boas práticas básicas

## 15. Fora do Escopo

- Upload de comprovantes pra S3 (campo `receipt_ref` reservado pra futuro)
- Multi-usuário, OAuth, perfis
- Notificações por email/push
- Mobile app nativo
- Exportar pra Excel (v2)
- Integração com bancos / Open Finance
- Tela de previsão de fluxo de caixa por mês

## 16. Critérios de Aceitação

1. Consigo cadastrar todos os 22 grupos do seed inicial via UI
2. Consigo lançar um item previsto e ver ele somar no dashboard
3. Consigo criar um lançamento manual e ele aparece no realizado
4. Consigo registrar o MCP server no Claude.ai como connector
5. Pelo chat do Claude, **com foto de NF**, consigo enviar → ver proposta → confirmar → gravar
6. Pelo chat do Claude, **com áudio**, consigo descrever uma compra → ver proposta → confirmar → gravar
7. Pelo chat do Claude, **com texto livre**, consigo descrever uma compra → ver proposta → confirmar → gravar
8. Após gravação via chat, o dashboard reflete o novo valor (com refresh manual tolerável)
9. Lançamento multi-grupo (uma NF com itens de 2+ grupos) cria N linhas distintas
10. Validação rejeita lançamentos com grupo inválido, valor zero/negativo, data futura
11. App roda em produção no EC2 com HTTPS via Caddy, deploy automatizado via GitHub Actions
12. Backup diário do Postgres pra S3 funciona e há script de restore documentado
13. `pytest` passa com cobertura mínima de 70% nas rotas e serviços
14. Consigo cadastrar 3 linhas no grupo "Vidraçaria" com fornecedores, descrições e prioridades diferentes (ex: box Luca/alta, box hóspedes/média, espelho hall/baixa)
15. Dashboard mostra "Previsto por Prioridade" com 3 cards (Alta/Média/Baixa) somando os valores corretamente; sem comparação com realizado nessa seção

## 17. Decisões em Aberto (definir antes do desenvolvimento)

| Decisão                                  | Default sugerido                | Marcar se diferente |
|------------------------------------------|---------------------------------|---------------------|
| AWS region                               | sa-east-1                       |                     |
| Tamanho da instância EC2                 | t4g.small (ARM)                 |                     |
| Domínio                                  | Duck DNS grátis (subdomínio)    |                     |
| IaC                                      | Terraform                       |                     |
| Auth do MCP                              | API key estática                |                     |
| Auth da UI web                           | Basic auth (1 usuário em env)   |                     |
| Frontend framework                       | Jinja + HTMX (sem SPA)          |                     |
| Banco                                    | PostgreSQL no próprio EC2       |                     |
| Container registry                       | GHCR                            |                     |
| Free Tier disponível?                    | Verificar conta AWS             |                     |

## 18. Entregáveis Esperados

1. Repositório GitHub com a estrutura acima
2. `README.md` com:
   - Setup local (docker-compose.dev.yml)
   - Setup do EC2 (Terraform + bootstrap)
   - Como gerar a API key e registrar o MCP no Claude.ai
   - Como restaurar backup
3. Diagrama de arquitetura (Mermaid no README)
4. OpenAPI auto-gerada pelo FastAPI em `/docs`
5. Script de bootstrap pra criar API key inicial

## 19. Estilo de Código

- Type hints obrigatórios
- Docstrings em funções públicas
- Nomes de variáveis e comentários em PT-BR OK; APIs e modelos em inglês pra consistência

---

**Importante:** este é um projeto **novo e independente**. Não reutilizar código, schemas, configurações ou padrões de outros projetos pessoais que eu já tenho. Começar do zero.
