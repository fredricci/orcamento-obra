#!/usr/bin/env bash
# restore.sh — Restaura backup do S3 para o banco PostgreSQL
# Uso: ./restore.sh 2026-06-07

set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-orcamento-obra-db-1}"
BUCKET_NAME="${BUCKET_NAME:?Variável BUCKET_NAME não definida}"
DB_NAME="${DB_NAME:-orcamento_obra}"
DB_USER="${DB_USER:-obra}"

if [[ $# -ne 1 ]]; then
    echo "Uso: $0 YYYY-MM-DD"
    echo "Exemplo: $0 2026-06-07"
    exit 1
fi

DATE="$1"
FILENAME="backup-${DATE}.sql.gz"
TMPFILE="/tmp/${FILENAME}"

log() {
    echo "[$(date -Iseconds)] $*"
}

log "Restore do backup: ${FILENAME}"
log "Destino: container=${DB_CONTAINER} banco=${DB_NAME}"
echo ""
echo "ATENÇÃO: esta operação é DESTRUTIVA e sobrescreverá todos os dados atuais do banco."
read -r -p "Digite 'sim' para confirmar: " CONFIRM

if [[ "${CONFIRM}" != "sim" ]]; then
    echo "Operação cancelada."
    exit 0
fi

# Download do S3
log "Baixando s3://${BUCKET_NAME}/${FILENAME}..."
if aws s3 cp "s3://${BUCKET_NAME}/${FILENAME}" "${TMPFILE}"; then
    log "Download concluído: ${TMPFILE} ($(du -sh "${TMPFILE}" | cut -f1))"
else
    log "ERRO: download do S3 falhou (verifique a data e o nome do bucket)"
    exit 1
fi

# Descomprime e restaura
log "Restaurando banco..."
if gunzip -c "${TMPFILE}" | docker exec -i "${DB_CONTAINER}" \
    psql -U "${DB_USER}" "${DB_NAME}"; then
    log "Restore concluído com sucesso."
else
    log "ERRO: restore falhou"
    rm -f "${TMPFILE}"
    exit 1
fi

rm -f "${TMPFILE}"
log "Arquivo temporário removido."
