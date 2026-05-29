#!/usr/bin/env bash
# Stage 24 restore guard for the AI Agents SWD platform.
#
# Refuses to run unless ALL of:
#
#   * a backup file is supplied as the first positional argument and
#     points to a real file on disk;
#   * the APP_ENV (or shell env) is NOT ``production`` /
#     ``production-check``;
#   * ALLOW_RESTORE=true is set in the invoking shell.
#
# Without that triple, the script prints the refusal reason and exits
# with code 1. The platform's destructive restore path is intentionally
# noisy.
#
# Run from the repository root:
#   ALLOW_RESTORE=true ./scripts/restore_postgres.sh backups/aiagents-20260529T120000Z.dump
set -uo pipefail

backup_file="${1:-}"

if [ -z "$backup_file" ]; then
  echo "USAGE: ALLOW_RESTORE=true $0 <backup-file>"
  echo "RESTORE_POSTGRES: FAIL (missing backup file argument)"
  exit 1
fi

if [ ! -f "$backup_file" ]; then
  echo "RESTORE_POSTGRES: FAIL (backup file not found: $backup_file)"
  exit 1
fi

APP_ENV_LOWER=$(printf "%s" "${APP_ENV:-local}" | tr '[:upper:]' '[:lower:]')
case "$APP_ENV_LOWER" in
  production|production-check)
    echo "RESTORE_POSTGRES: FAIL (APP_ENV=$APP_ENV_LOWER — restore is forbidden in this mode)"
    exit 1
    ;;
esac

if [ "${ALLOW_RESTORE:-false}" != "true" ]; then
  echo "RESTORE_POSTGRES: FAIL (ALLOW_RESTORE!=true — set ALLOW_RESTORE=true to confirm overwrite)"
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"

echo "### restore_postgres start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "restoring ${backup_file} -> ${POSTGRES_SERVICE}/${POSTGRES_DB}"

# pg_restore with --clean and --if-exists drops + recreates owned
# objects before reapplying. -1 wraps the restore in a single
# transaction so a partial failure rolls back.
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore --clean --if-exists -1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  < "$backup_file"

rc=$?
if [ "$rc" -ne 0 ]; then
  echo "RESTORE_POSTGRES: FAIL (pg_restore rc=$rc)"
  exit "$rc"
fi
echo "RESTORE_POSTGRES_DONE: PASS"
