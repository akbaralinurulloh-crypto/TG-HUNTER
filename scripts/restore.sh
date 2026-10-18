#!/bin/bash
# ==============================================================================
# MUHTASHAM TELEGRAM AI AGENT — POSTGRESQL ZAXIRA NUSXANI TIKLASH SKRIPTI (AT-12)
# ==============================================================================
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Foydalanish: $0 <zaxira_fayli.sql.gz> [maqsad_baza_nomi]"
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="${2:-${POSTGRES_DB:-muhtasham_db}}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-postgres}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Xatolik: $BACKUP_FILE fayli topilmadi!"
    exit 1
fi

echo "[$(date)] Tiklash boshlandi: $BACKUP_FILE -> $TARGET_DB..."

export PGPASSWORD="${POSTGRES_PASSWORD:-}"

# Bazaga yuklash
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$TARGET_DB"

echo "[$(date)] Ma'lumotlar muvaffaqiyatli tiklandi: $TARGET_DB"
