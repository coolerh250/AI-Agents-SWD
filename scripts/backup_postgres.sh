#!/usr/bin/env bash
# Stage 24 backup baseline for the AI Agents SWD platform.
#
# Produces a timestamped `pg_dump --format=custom` archive of the
# ``aiagents`` database into ``./backups/``. The archive is BINARY
# (-Fc) so restore can use selective `pg_restore` flags.
#
# Local/test only. The script assumes the existing compose stack is
# running and contacts the postgres container via `docker exec`. It
# never writes a secret into the backup filename and never logs the
# database password (the local cluster uses trust auth).
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

mkdir -p "$BACKUP_DIR"

ts=$(date -u +"%Y%m%dT%H%M%SZ")
out="$BACKUP_DIR/aiagents-${ts}.dump"

echo "### backup_postgres start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "target: ${POSTGRES_SERVICE}/${POSTGRES_DB} -> ${out}"

# The dump streams via `docker compose exec -T` so the binary archive
# isn't mangled by an interactive TTY. We never echo the password —
# this is local/test trust auth, but the same call works once a
# password is supplied via PGPASSWORD (the script intentionally does
# NOT read PGPASSWORD here; see backup_postgres_with_password if you
# need that path).
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$out"

rc=$?
if [ "$rc" -ne 0 ]; then
  echo "BACKUP_FAILED rc=$rc"
  rm -f "$out"
  exit "$rc"
fi

size=$(wc -c < "$out" 2>/dev/null | tr -d '[:space:]')
echo "backup_file=$out size_bytes=$size"
echo "BACKUP_POSTGRES_DONE: PASS"
