#!/bin/bash
# ==============================================================================
# MUHTASHAM TELEGRAM AI AGENT — POSTGRESQL AVTOMATIK ZAXIRA NUSXA OLISH SKRIPTI
# ==============================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
mkdir -p "$BACKUP_DIR"

DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/muhtasham_db_$DATE.sql.gz"

DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-muhtasham_db}"

echo "[$(date)] Zaxira nusxa olish boshlandi: $DB_NAME..."

export PGPASSWORD="${POSTGRES_PASSWORD:-}"

# pg_dump orqali ma'lumotlarni chiqarish va gzip bilan siqish
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

# Fayl hajmini tekshirish
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Zaxira nusxa muvaffaqiyatli saqlandi: $BACKUP_FILE (Hajmi: $BACKUP_SIZE)"

# 7 kundan eski zaxira nusxalarni o'chirish
find "$BACKUP_DIR" -name "muhtasham_db_*.sql.gz" -type f -mtime +7 -delete
echo "[$(date)] 7 kundan eski nusxalar tozalandi."
