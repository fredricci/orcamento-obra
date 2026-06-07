# Prompts para Claude Code — App de Orçamento de Obra

Este arquivo contém os prompts pra cada turno de trabalho no Claude Code, na ordem recomendada. Cada turno é focado e tem critério de aceitação claro. Use um por vez e valide antes de seguir pro próximo.

---

## Pré-requisitos antes de começar

- [ ] Claude Code instalado (`claude doctor` mostra tudo OK)
- [ ] `SPEC.md` (o arquivo `SPEC_orcamento_obra_v3.md` renomeado) na raiz do diretório do projeto
- [ ] `git init` feito na pasta
- [ ] Docker Desktop rodando (pra testes locais)
- [ ] Conta AWS com permissões pra EC2/S3/IAM (pro turno 6+)
- [ ] Conta GitHub com repo criado (público ou privado) (pro turno 6+)

---

## Como usar

1. Abre o terminal na pasta do projeto e roda `claude`
2. Cola o prompt do turno desejado
3. Acompanha a execução, responde perguntas que ele fizer
4. Quando terminar, **valida o critério de aceitação** descrito no fim do prompt
5. Faz `git add . && git commit -m "..."` pra marcar progresso
6. Limpa o contexto com `/clear` antes de começar o próximo turno (pra não acumular ruído)
7. Cola o próximo

---

## Turno 1 — Foundation: estrutura, models, Docker, /groups

```
Estou começando um projeto novo do zero — app de controle de orçamento da
minha obra. A especificação completa está em `SPEC.md` na raiz desse
diretório. Lê ela inteira antes de começar.

Pra esse primeiro turno, faz o seguinte e SÓ ISSO:

1. Cria a estrutura inicial do repo conforme §12 da spec (pastas vazias com
   .gitkeep onde precisar)
2. Implementa `Dockerfile` multi-stage e `docker-compose.dev.yml` (com
   Postgres pra dev local, volume nomeado, healthcheck)
3. Configura `pyproject.toml` com FastAPI, SQLAlchemy 2.x, Alembic, Pydantic,
   structlog, pytest, pytest-asyncio, httpx, ruff, black
4. Implementa os 3 models (`groups`, `budget_items`, `transactions`) em
   `app/models/` exatamente conforme §4 da spec, incluindo enums, indexes e
   FKs
5. Configura Alembic e gera a 1ª migration cobrindo as 3 tabelas + seed
   dos 24 grupos com `sort_order` preenchido
6. CRUD básico de `/api/v1/groups` (GET, POST, PUT, DELETE soft) — sem auth
   por enquanto
7. 2-3 testes pytest cobrindo o CRUD de groups
8. `README.md` com instruções de "como rodar local" (docker compose up,
   migrations, primeira request curl)
9. `.gitignore`, `.env.example`, `.dockerignore`

NÃO toque em: deploy AWS, MCP server, UI web, outros endpoints, CI/CD,
Terraform, autenticação. Esses vão em turnos futuros.

Critério de aceitação: eu rodo `docker compose -f docker-compose.dev.yml up`,
faço `curl localhost:8000/api/v1/groups` e vejo os 24 grupos retornados em
JSON. `pytest` passa.

Quando terminar, lista o que ficou pra fazer pros próximos turnos.
```

---

## Turno 2 — CRUD completo: budget_items e transactions

```
Continuando do turno anterior. Lê o SPEC.md e o estado atual do repo.

Nesse turno, implementa:

1. CRUD completo de `/api/v1/budget-items` conforme §5 da spec, incluindo
   filtro `?group_id=` e validação de FK contra `groups`
2. CRUD completo de `/api/v1/transactions` conforme §5, incluindo:
   - Aceitar array no POST (lançamento multi-grupo numa mesma chamada)
   - Filtros `?group_id=`, `?start_date=`, `?end_date=`, `?limit=`
   - Validações: `value > 0`, `transaction_date <= hoje`, `group_id` existe,
     `payment_method` e `input_type` em enums válidos
3. Schemas Pydantic separados para input (CreateTransaction) e output
   (TransactionRead), evitando expor campos internos desnecessariamente
4. Testes pytest cobrindo:
   - Caminho feliz dos dois CRUDs
   - Validações negativas (valor zero, data futura, grupo inexistente,
     payment_method inválido)
   - Filtros de transactions (período, grupo)
   - POST com array de N items
5. Atualizar README com exemplos de curl pros novos endpoints

NÃO toque em: dashboard, UI, MCP, deploy, auth.

Critério de aceitação: consigo criar via curl 3 budget_items no grupo
"Vidraçaria" com prioridades diferentes (alta/média/baixa). Consigo criar
um POST de transactions com array de 2 items em grupos diferentes. Pytest
passa com cobertura >= 70% nas rotas/services.
```

---

## Turno 3 — Dashboard endpoints

```
Continuando. Lê SPEC.md (§5 Dashboard) e o estado do repo.

Implementa:

1. `GET /api/v1/dashboard/summary` retornando totais gerais conforme spec
2. `GET /api/v1/dashboard/by-group` retornando quebra por grupo (planned,
   realized, balance, percent_executed, is_over_budget) — todos os grupos
   ativos, mesmo os sem lançamentos (retorna 0 nos valores)
3. `GET /api/v1/dashboard/by-priority` retornando agregação SÓ DO PREVISTO
   por prioridade (alta/media/baixa) com items_count. Não tentar inferir
   realizado por prioridade — isso foi decisão consciente da spec (§5)
4. Garantir que as queries usam os indexes definidos em §4 (rodar
   `EXPLAIN ANALYZE` numa migration de teste pra confirmar)
5. Testes pytest:
   - Cenário com 5+ budget_items em 3 grupos diferentes + 4 transactions
   - Assert que `summary.balance = planned - realized`
   - Assert que grupo sem transactions retorna 0/0/0
   - Assert que grupo que estourou tem `is_over_budget=true` e
     `percent_executed > 1.0`
   - Assert que `by-priority` soma corretamente os 3 níveis

NÃO toque em: UI, MCP, deploy, auth.

Critério de aceitação: faço curl nos 3 endpoints, vejo respostas
condizentes com os dados de seed. Pytest passa.
```

---

## Turno 4 — UI Web (Jinja + HTMX + Tailwind)

```
Continuando. Lê SPEC.md (§7 Telas e §3 Arquitetura) e o estado do repo.

Implementa a UI server-rendered:

1. Setup do Tailwind via CDN ou via build local (CDN é OK pra começar,
   mais simples). HTMX via CDN também.
2. Layout base em `app/templates/base.html` com nav lateral ou topo,
   estilo limpo, mobile-friendly
3. Tela `/` (Dashboard) conforme §7:
   - Card com os 4 totais (previsto/realizado/saldo/%)
   - Tabela por grupo com saldo negativo em vermelho
   - Seção "Previsto por Prioridade" com 3 cards (Alta/Média/Baixa)
   - Gráfico de barras horizontal (pode usar Chart.js via CDN ou só HTML/CSS
     bars — o que for mais simples)
4. Tela `/grupos`:
   - Listagem
   - Botão "Adicionar grupo" com modal/inline form via HTMX
   - Editar inline
   - Toggle ativo/inativo
5. Tela `/previsto`:
   - Filtros por grupo e por prioridade
   - Tabela com soma total no rodapé
   - Adicionar/editar/deletar via HTMX (sem full page reload)
6. Tela `/realizado`:
   - Filtros: grupo, período, origem, tipo de input
   - Tabela com paginação simples (limit/offset, padrão 50)
   - Botão "Lançamento manual" abrindo modal
7. Basic auth via middleware FastAPI: usuário/senha vindos de env vars
   `WEB_USER`/`WEB_PASSWORD`. Aplicar SÓ nas rotas `/` `/grupos` `/previsto`
   `/realizado` — manter `/api/v1/*` sem auth básica (vai ter API key
   no próximo turno)
8. 2-3 testes de integração das rotas web (renderiza 200, contém elementos
   esperados)

NÃO toque em: MCP, deploy, API key auth.

Critério de aceitação: abro localhost:8000 no browser, vejo o dashboard
com os dados que cadastrei, consigo navegar entre as 4 telas, criar/editar/
deletar registros sem erros, e a basic auth bloqueia se eu não autenticar.
```

---

## Turno 5 — MCP Server + API Key auth

```
Continuando. Lê SPEC.md (§6 Integração MCP) e o estado do repo.

Implementa:

1. Middleware de API key pra TODAS as rotas `/api/v1/*` e `/mcp/v1/*`:
   - Header `X-API-Key`
   - Chave vinda de env var `API_KEY`
   - Retorna 401 se ausente/inválida
2. MCP server em `/mcp/v1` seguindo o protocolo Model Context Protocol.
   Usa biblioteca oficial Python (`mcp` ou `fastmcp`, o que estiver mais
   maduro hoje). Implementa as 4 tools de §6:
   - `list_groups()`
   - `get_budget_overview()`
   - `create_transactions(items)` — só após confirmação no chat; valida
     `group_name` exato contra `groups.name`, retorna erro com lista de
     grupos válidos se não bater
   - `list_recent_transactions(limit=10)`
3. A tool `create_transactions` deve retornar tanto os items criados quanto
   `updated_balances` (do grupo afetado), conforme spec
4. Script `scripts/bootstrap.py` que gera uma API key aleatória, imprime
   na tela com instruções de como adicionar no `.env` e como registrar
   o MCP server como custom connector no Claude.ai
5. Testes pytest pra:
   - 401 quando falta API key
   - Cada tool MCP funciona end-to-end
   - `create_transactions` rejeita group_name inválido com mensagem útil
   - `create_transactions` aceita array multi-grupo
6. Atualizar README com seção "Como registrar o MCP server no Claude.ai"

NÃO toque em: deploy, CI/CD.

Critério de aceitação: rodando localmente, consigo fazer curl com
`X-API-Key: <chave>` e bater nos 4 endpoints MCP. Sem o header, recebo
401. Pytest passa.
```

---

## Turno 6 — Infraestrutura: Terraform + deploy config

```
Continuando. Lê SPEC.md (§10 Infraestrutura Opção A) e o estado do repo.

Implementa em pasta `infra/`:

1. Terraform pra Opção A (low-cost):
   - `main.tf`: EC2 t4g.small em sa-east-1, Ubuntu 22.04 ARM AMI, key pair
     existente (variável `key_pair_name`), Security Group com 22 (restrito
     a `my_ip` variable) e 443 público, EBS gp3 20GB, Elastic IP
   - `s3.tf`: bucket pra backups com lifecycle (30d → IA, 90d → Glacier)
   - `iam.tf`: role da EC2 com policy de write no bucket de backup
   - `variables.tf`: region, key_pair_name, my_ip, project_name
   - `outputs.tf`: public_ip, ec2_instance_id, backup_bucket_name
   - `README.md` em `infra/` com instruções de `terraform init/plan/apply`
2. Em `deploy/`:
   - `docker-compose.yml` pra produção (app + postgres + caddy, com
     restart=always, healthchecks, named volumes)
   - `Caddyfile` configurando HTTPS automático pro domínio (variável)
     e reverse proxy pra app:8000
   - `backup.sh`: shell script que faz pg_dump, comprime com gzip e
     `aws s3 cp` pro bucket de backup, com data no nome do arquivo
   - `restore.sh`: script reverso (baixa do S3, descomprime, restora)
   - `systemd/backup.service` e `systemd/backup.timer` rodando o
     backup.sh diariamente às 3am
3. Em `README.md` raiz, adicionar seção "Deploy em produção" com passo a
   passo: terraform apply → SSH no host → clone repo → criar .env →
   docker compose up -d → instalar systemd timer

NÃO faça `terraform apply` agora (custo!). Só gere os arquivos. Eu rodo
manualmente quando estiver tudo revisado.

NÃO toque em: GitHub Actions ainda.

Critério de aceitação: `terraform validate` passa em `infra/`. Arquivos
estão completos e o passo a passo do README é executável.
```

---

## Turno 7 — CI/CD GitHub Actions + finalização

```
Continuando. Lê SPEC.md (§11 CI/CD) e o estado do repo.

Implementa:

1. `.github/workflows/ci.yml`:
   - Trigger: push e PR
   - Jobs: lint (ruff + black), test (pytest com Postgres em service
     container), build (build do Docker image, sem push)
   - Cache de pip
2. `.github/workflows/deploy.yml`:
   - Trigger: push na `main` após CI passar
   - Build da imagem
   - Login no GHCR usando GITHUB_TOKEN
   - Push pra `ghcr.io/<owner>/orcamento-obra:latest` + tag com commit SHA
   - SSH no EC2 usando secret `SSH_PRIVATE_KEY`, `SSH_HOST`, `SSH_USER`
   - Comandos no host: `docker compose pull && docker compose up -d &&
     docker image prune -f`
3. Documentar no README quais secrets do GitHub precisam ser criados e
   como obter cada um
4. Adicionar status badge do CI no README
5. Configurar Dependabot básico (`.github/dependabot.yml`) pra atualizar
   deps Python e Docker semanalmente
6. Revisar a cobertura geral de testes; se estiver abaixo de 70%, adicionar
   testes onde faltam

Critério de aceitação: faço push de um commit pequeno na main, vejo CI
passar no GitHub, vejo deploy.yml rodar e o EC2 atualizar a imagem. App
continua respondendo HTTPS depois do deploy.
```

---

## Dicas gerais durante os turnos

- **Use `/clear` entre turnos** pra resetar o contexto e evitar que o Claude carregue baggage de turnos anteriores
- **Revisa antes de commitar**: depois de cada turno, abra os arquivos principais e dá uma lida. Se algo parece estranho, pergunta antes de aceitar
- **Não pule a validação local**: o critério de aceitação no fim de cada prompt existe pra você conferir antes de seguir
- **Pergunte se ele atalhar**: às vezes o Claude pula testes ou simplifica demais. Pode perguntar "você implementou todos os filtros mencionados?" e ele revisita
- **Commits pequenos**: faz `git commit` no fim de cada turno com mensagem descritiva. Se algo dá errado depois, é fácil voltar
- **Custos AWS**: só faz `terraform apply` quando tiver tudo pronto, e fica de olho no AWS Cost Explorer nos primeiros dias

---

## Se algo der errado

- **Claude Code travou ou ficou repetitivo**: `/clear` e cola o prompt do turno de novo, mais conciso
- **Migração Alembic deu conflito**: peça pra ele rodar `alembic downgrade base` e regenerar
- **Postgres não sobe local**: confere se a porta 5432 não está em uso (você tem o gestor financeiro rodando talvez)
- **GHCR push falha**: confere as permissões do `GITHUB_TOKEN` (Settings → Actions → General → Workflow permissions → Read and write)

---

Boa sorte. Quando terminar todos os turnos, você vai ter:

- Repo no GitHub com app completo
- App rodando em produção numa EC2 com HTTPS
- Dashboard funcional via web
- Integração MCP no Claude.ai onde você manda foto/áudio/texto da NF e tem o lançamento gravado
- Backup diário automático
- CI/CD funcionando
- Custo mensal: ~US$14-16 (ou US$0 se ainda tiver Free Tier)
