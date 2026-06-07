#!/usr/bin/env bash
# bootstrap.sh — Setup inicial do EC2 para o orcamento-obra
# Executar após o primeiro SSH no servidor.
# Uso: bash bootstrap.sh

set -euo pipefail

APP_DIR="/opt/orcamento-obra"
REPO_URL="${REPO_URL:-https://github.com/SEU_USUARIO/orcamento-obra.git}"

log() {
    echo "[$(date -Iseconds)] $*"
}

log "=== Bootstrap do orcamento-obra ==="

# ── 1. Instalar Docker ──────────────────────────────────────────────────────

log "Instalando Docker..."
apt-get update -qq
apt-get install -y -qq \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker ubuntu
systemctl enable docker
systemctl start docker

log "Docker instalado: $(docker --version)"
log "Docker Compose instalado: $(docker compose version)"

# ── 2. Instalar AWS CLI ──────────────────────────────────────────────────────

log "Instalando AWS CLI..."
apt-get install -y -qq unzip
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
rm -rf /tmp/awscliv2.zip /tmp/aws
log "AWS CLI instalado: $(aws --version)"

# ── 3. Criar diretório do app ────────────────────────────────────────────────

log "Criando diretório ${APP_DIR}..."
mkdir -p "${APP_DIR}"
chown ubuntu:ubuntu "${APP_DIR}"

# ── 4. Clonar repositório ────────────────────────────────────────────────────

log "Clonando repositório..."
if [[ -d "${APP_DIR}/.git" ]]; then
    log "Repositório já existe, fazendo git pull..."
    sudo -u ubuntu git -C "${APP_DIR}" pull
else
    sudo -u ubuntu git clone "${REPO_URL}" "${APP_DIR}"
fi

# ── 5. Arquivo .env ──────────────────────────────────────────────────────────

cat <<'EOF'

============================================================
PRÓXIMO PASSO: criar o arquivo .env em /opt/orcamento-obra/deploy/.env

Copie o template abaixo, preencha os valores e salve com modo 600:

  nano /opt/orcamento-obra/deploy/.env
  chmod 600 /opt/orcamento-obra/deploy/.env

Conteúdo do .env:
------------------------------------------------------------
GHCR_OWNER=seu_usuario_github
DOMAIN=obra.duckdns.org

# Banco de dados
POSTGRES_DB=orcamento_obra
POSTGRES_USER=obra
POSTGRES_PASSWORD=<senha_aleatória>

# Aplicação
API_KEY=<chave_api_aleatória_para_rest_e_mcp>
BASIC_AUTH_USER=admin
BASIC_AUTH_PASSWORD=<senha_aleatória>

# Backup S3
BUCKET_NAME=<nome_do_bucket_do_terraform_output>
DB_CONTAINER=deploy-db-1
DB_NAME=orcamento_obra
DB_USER=obra
------------------------------------------------------------

Para gerar senhas aleatórias:
  openssl rand -hex 32

============================================================
EOF

# ── 6. Subir os containers ───────────────────────────────────────────────────

if [[ -f "${APP_DIR}/deploy/.env" ]]; then
    log "Arquivo .env encontrado, subindo containers..."
    cd "${APP_DIR}/deploy"
    sudo -u ubuntu docker compose pull
    sudo -u ubuntu docker compose up -d
    log "Containers rodando:"
    docker compose ps
else
    log "AVISO: .env não encontrado. Crie o arquivo e execute manualmente:"
    log "  cd ${APP_DIR}/deploy && docker compose up -d"
fi

# ── 7. Configurar cron de backup ─────────────────────────────────────────────

log "Configurando cron de backup diário às 3am..."
CRON_LINE="0 3 * * * ubuntu bash ${APP_DIR}/deploy/backup.sh >> /var/log/orcamento-backup.log 2>&1"

if crontab -l 2>/dev/null | grep -qF "${APP_DIR}/deploy/backup.sh"; then
    log "Cron já configurado, pulando."
else
    (crontab -l 2>/dev/null; echo "${CRON_LINE}") | crontab -
    log "Cron configurado: ${CRON_LINE}"
fi

log "=== Bootstrap concluído ==="
log "Não esqueça de:"
log "  1. Criar/verificar o .env em ${APP_DIR}/deploy/.env"
log "  2. Apontar o DNS do seu domínio para o Elastic IP"
log "  3. Rodar: cd ${APP_DIR}/deploy && docker compose up -d"
