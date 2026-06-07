#!/usr/bin/env bash
# backup.sh — pg_dump do banco para S3
# Configurar as variáveis abaixo ou exportá-las antes de executar o script.

set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-orcamento-obra-db-1}"
BUCKET_NAME="${BUCKET_NAME:?Variável BUCKET_NAME não definida}"
DB_NAME="${DB_NAME:-orcamento_obra}"
DB_USER="${DB_USER:-obra}"

DATE=$(date +%Y-%m-%d)
FILENAME="backup-${DATE}.sql.gz"
TMPFILE="/tmp/${FILENAME}"

log() {
    echo "[$(date -Iseconds)] $*"
}

log "Iniciando backup do banco ${DB_NAME}..."

# Dump comprimido direto para o arquivo temporário
if docker exec "${DB_CONTAINER}" \
    pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${TMPFILE}"; then
    log "pg_dump concluído: ${TMPFILE} ($(du -sh "${TMPFILE}" | cut -f1))"
else
    log "ERRO: pg_dump falhou"
    rm -f "${TMPFILE}"
    exit 1
fi

# Upload para S3
log "Enviando para s3://${BUCKET_NAME}/${FILENAME}..."
if aws s3 cp "${TMPFILE}" "s3://${BUCKET_NAME}/${FILENAME}" \
    --storage-class STANDARD; then
    log "Upload concluído: s3://${BUCKET_NAME}/${FILENAME}"
else
    log "ERRO: upload para S3 falhou"
    rm -f "${TMPFILE}"
    exit 1
fi

rm -f "${TMPFILE}"
log "Backup finalizado com sucesso."
