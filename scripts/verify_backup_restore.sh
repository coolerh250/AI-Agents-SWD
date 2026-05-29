#!/usr/bin/env bash
# Stage 24 backup/restore smoke. Local/test only.
#
# The script:
#   1. takes a fresh schema-shape snapshot of the live ``aiagents`` DB
#      (table count) so we can assert it after the smoke;
#   2. runs ``scripts/backup_postgres.sh`` and confirms the archive is
#      a valid PostgreSQL custom-format dump (``pg_restore -l`` parses);
#   3. asserts the existing DB is intact (table count unchanged) —
#      ``backup_postgres.sh`` is read-only by design;
#   4. asserts ``scripts/restore_postgres.sh`` REFUSES without
#      ``ALLOW_RESTORE=true``;
#   5. cleans up the temporary backup file.
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"

echo "### verify_backup_restore start: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# 1. snapshot table count BEFORE
before=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  tables_before=$before"

# 2. run backup
./scripts/backup_postgres.sh 2>&1 | tail -10
latest=$(ls -1t backups/aiagents-*.dump 2>/dev/null | head -n1 || true)
if [ -z "$latest" ] || [ ! -f "$latest" ]; then
  echo "BACKUP_RESTORE_VERIFY: FAIL (no dump produced)"
  exit 1
fi
echo "  backup_file=$latest"

# 3. validate dump is parseable (pg_restore -l reads the TOC)
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  bash -c "cat > /tmp/aiagents-verify.dump" < "$latest" 2>/dev/null
toc_lines=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore -l /tmp/aiagents-verify.dump 2>/dev/null | wc -l | tr -d '[:space:]')
echo "  pg_restore_toc_lines=$toc_lines"
if [ -z "$toc_lines" ] || [ "$toc_lines" -lt 5 ]; then
  echo "BACKUP_RESTORE_VERIFY: FAIL (pg_restore -l produced no TOC)"
  rm -f "$latest"
  exit 1
fi

# 4. snapshot table count AFTER (must match BEFORE — backup is read-only)
after=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  tables_after=$after"
if [ "$before" != "$after" ]; then
  echo "BACKUP_RESTORE_VERIFY: FAIL (table count changed: before=$before after=$after)"
  exit 1
fi

# 5. restore refusal without ALLOW_RESTORE
refusal=$(./scripts/restore_postgres.sh "$latest" 2>&1 | tail -3 | tr -d '\r')
echo "  restore_refusal: $refusal"
if ! echo "$refusal" | grep -q "ALLOW_RESTORE!=true"; then
  echo "BACKUP_RESTORE_VERIFY: FAIL (restore did not refuse without ALLOW_RESTORE=true)"
  exit 1
fi

# 6. cleanup
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  rm -f /tmp/aiagents-verify.dump >/dev/null 2>&1 || true

echo
echo "  backup_file_size=$(wc -c < "$latest" 2>/dev/null | tr -d '[:space:]')"
echo "BACKUP_RESTORE_VERIFY: PASS"
