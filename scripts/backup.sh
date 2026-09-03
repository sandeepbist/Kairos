#!/usr/bin/env bash
# Kairos Postgres backup: pg_dump -Fc + paired key file + retention.
#
# Usage: ./scripts/backup.sh                     # dev (host port 5435)
#        KAIROS_BACKUP_IN_COMPOSE=1 ./scripts/backup.sh   # prod (via compose exec)
#
# The dump contains Fernet-encrypted vault rows (OAuth tokens, webhook
# secrets) — it is useless without the ENCRYPTION_KEY. This script writes
# the matching key next to every dump with 0600 perms so a restore never
# depends on memory. Keep backups/ OUT of any sync target: the plaintext
# key sits beside it.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${KAIROS_BACKUP_DIR:-$ROOT_DIR/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RETENTION_DAYS="${KAIROS_BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
DUMP="$BACKUP_DIR/kairos-$STAMP.dump"

# Source Postgres coordinates from .env (the same values compose uses).
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

PG_USER="${POSTGRES_USER:-kairos_user}"
PG_DB="${POSTGRES_DB:-kairos_db}"

if [ -n "${KAIROS_BACKUP_IN_COMPOSE:-}" ]; then
  compose_file="${COMPOSE_FILE:-docker-compose.prod.yml}"
  docker compose -f "$ROOT_DIR/$compose_file" exec -T postgres \
    pg_dump -U "$PG_USER" -Fc "$PG_DB" > "$DUMP"
else
  PGPORT="${POSTGRES_PORT:-5435}" pg_dump -U "$PG_USER" \
    -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5435}" -Fc "$PG_DB" > "$DUMP"
fi

# Pair the dump with its key — the two are worthless apart.
if [ -n "${ENCRYPTION_KEY:-}" ]; then
  printf '%s' "$ENCRYPTION_KEY" > "$DUMP.key"
  chmod 600 "$DUMP.key"
fi

# Retention (dumps and their keys prune together).
find "$BACKUP_DIR" -name 'kairos-*.dump' -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'kairos-*.dump.key' -mtime "+$RETENTION_DAYS" -delete

echo "Backup written: $DUMP"
if [ -f "$DUMP.key" ]; then
  echo "Paired key:    $DUMP.key (0600)"
fi
echo "WARNING: a restore needs the dump AND its key together — losing"
echo "either loses every connector credential and all history."
