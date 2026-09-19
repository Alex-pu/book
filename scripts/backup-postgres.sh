#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

: "${DATABASE_URL:?DATABASE_URL must be set in .env or the environment}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/spa-booking}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
DATABASE_URL="${DATABASE_URL//+asyncpg/}"
pg_dump --format=custom --file="$BACKUP_DIR/spa-booking-$STAMP.dump" "$DATABASE_URL"
find "$BACKUP_DIR" -type f -name 'spa-booking-*.dump' -mtime "+$RETENTION_DAYS" -delete

echo "Created PostgreSQL backup in $BACKUP_DIR"
