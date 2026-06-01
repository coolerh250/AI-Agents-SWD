#!/usr/bin/env bash
# Stage 25 staging backup / restore smoke. The script:
#
#   1. snapshots the staging DB's public table count;
#   2. runs `pg_dump --format=custom` against the staging Postgres
#      (password auth);
#   3. verifies `pg_restore -l` parses the resulting archive's TOC;
#   4. asserts the staging DB's table count is unchanged (backup is
#      read-only);
#   5. asserts `scripts/restore_postgres.sh` refuses without
#      ``ALLOW_RESTORE=true``;
#   6. confirms the staging operation NEVER touched the local/test
#      aiagents-test DB (its table count is sampled before + after).
#
# Run from the repository root. Assumes the staging stack is already
# up; if it isn't, the script exits with FAIL and asks the operator to
# run scripts/start_staging_runtime.sh first.
set -uo pipefail

PROJECT="${STAGING_COMPOSE_PROJECT:-aiagents-staging}"
COMPOSE_FILE="${STAGING_COMPOSE_FILE:-infra/docker-compose/docker-compose.staging.yml}"
ENV_FILE="${STAGING_ENV_FILE:-infra/runtime/.env.staging.local}"
COMPOSE="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"
LOCAL_COMPOSE="docker compose -p aiagents-test -f infra/docker-compose/docker-compose.yml"

BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$BACKUP_DIR"

echo "### verify_staging_backup_restore: $(date '+%Y-%m-%d %H:%M:%S %Z')"

if [ ! -f "$ENV_FILE" ]; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (env file $ENV_FILE missing — run start_staging_runtime.sh first)"
  exit 1
fi

pg_user=$(grep -E '^STAGING_POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- || true)
pg_user="${pg_user:-aiagents_app}"
pg_db=$(grep -E '^STAGING_POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- || true)
pg_db="${pg_db:-aiagents}"

# Confirm staging postgres is up.
if ! $COMPOSE --env-file "$ENV_FILE" exec -T postgres pg_isready -U "$pg_user" -d "$pg_db" >/dev/null 2>&1; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (staging postgres not reachable — run start_staging_runtime.sh first)"
  exit 1
fi

# 1. table count BEFORE — staging
staging_before=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  psql -U "$pg_user" -d "$pg_db" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  staging tables_before=$staging_before"

# 1b. table count BEFORE — local/test (regression guard)
local_before=$($LOCAL_COMPOSE exec -T postgres \
  psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  local/test tables_before=$local_before"

# 2. run pg_dump against staging postgres
ts=$(date -u +"%Y%m%dT%H%M%SZ")
out="$BACKUP_DIR/aiagents-staging-${ts}.dump"
echo "  staging backup target: $out"

if ! $COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  pg_dump -U "$pg_user" -d "$pg_db" -Fc > "$out" 2>/dev/null; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (pg_dump failed)"
  rm -f "$out"
  exit 1
fi
size=$(wc -c < "$out" 2>/dev/null | tr -d '[:space:]')
echo "  staging backup size_bytes=$size"
if [ -z "$size" ] || [ "$size" -lt 1000 ]; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (backup too small)"
  rm -f "$out"
  exit 1
fi

# 3. pg_restore -l can parse the archive's TOC. Copy the file INTO the
# staging postgres container (it doesn't need access to the running DB)
# so pg_restore can read it.
$COMPOSE --env-file "$ENV_FILE" exec -T postgres bash -c "cat > /tmp/aiagents-staging-verify.dump" < "$out" 2>/dev/null
toc_lines=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  pg_restore -l /tmp/aiagents-staging-verify.dump 2>/dev/null | wc -l | tr -d '[:space:]')
echo "  staging pg_restore_toc_lines=$toc_lines"
if [ -z "$toc_lines" ] || [ "$toc_lines" -lt 5 ]; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (pg_restore -l produced no TOC)"
  rm -f "$out"
  exit 1
fi

# 4. staging table count AFTER (must match BEFORE)
staging_after=$($COMPOSE --env-file "$ENV_FILE" exec -T postgres \
  psql -U "$pg_user" -d "$pg_db" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  staging tables_after=$staging_after"
if [ "$staging_before" != "$staging_after" ]; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (staging table count changed)"
  rm -f "$out"
  exit 1
fi

# 5. restore refusal without ALLOW_RESTORE
refusal=$(./scripts/restore_postgres.sh "$out" 2>&1 | tail -3 | tr -d '\r')
echo "  restore refusal: $refusal"
if ! echo "$refusal" | grep -q "ALLOW_RESTORE!=true"; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (restore did not refuse without ALLOW_RESTORE=true)"
  rm -f "$out"
  exit 1
fi

# 6. local/test table count AFTER (regression guard — the script never
# touches local/test)
local_after=$($LOCAL_COMPOSE exec -T postgres \
  psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '[:space:]')
echo "  local/test tables_after=$local_after"
if [ "$local_before" != "$local_after" ]; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (local/test DB touched! before=$local_before after=$local_after)"
  rm -f "$out"
  exit 1
fi

# 7. cleanup the staging-internal copy
$COMPOSE --env-file "$ENV_FILE" exec -T postgres rm -f /tmp/aiagents-staging-verify.dump >/dev/null 2>&1 || true

# 8. Stage 26 — leak scan over docs / runtime-health logs / scripts.
# Doesn't read the backup file (custom-format pg_dump is binary).
echo
echo "=== Stage 26 secret-leak scan ==="
if ! ./scripts/scan_for_secret_leaks.sh 2>&1 | tail -3; then
  echo "STAGING_BACKUP_RESTORE_VERIFY: FAIL (secret leak scan failed)"
  rm -f "$out"
  exit 1
fi

echo
echo "  backup_file=$out (kept; gitignored)"
echo "STAGING_BACKUP_RESTORE_VERIFY: PASS"
