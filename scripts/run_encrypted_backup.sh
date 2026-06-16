#!/usr/bin/env bash
# Stage 51 -- encrypted backup producer (TEST / DEV ONLY).
#
# Flow:
#   1. ensure a test-only key file (scripts/setup_backup_dr_test_key.sh)
#   2. pg_dump the test database (docker compose exec postgres) -> runtime dir
#   3. openssl AES-256-CBC encrypt the dump -> runtime dir
#   4. compute sha256 of plain + encrypted artifacts
#   5. gather schema_migration_count / table_count / row counts
#   6. write a secret-free facts JSON (.runtime/backup-dr/facts.json)
#
# Hard rules:
#   * Refuses environment=production.
#   * Artifacts live under a runtime / gitignored dir; never committed.
#   * The key value is never printed; only the key_id label.
#
# Markers: BACKUP_ENCRYPTED_PRODUCE: PASS / FAIL  (prints facts_path=...)
set -uo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
COMPOSE="${COMPOSE:-docker compose -f infra/docker-compose/docker-compose.yml}"
PG_SERVICE="${POSTGRES_SERVICE:-postgres}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-aiagents}"
ENVIRONMENT="${BACKUP_DR_ENVIRONMENT:-test}"
RUNTIME_DIR="${BACKUP_DR_RUNTIME_DIR:-.runtime}/backup-dr"
KEY_FILE="${BACKUP_DR_TEST_KEY_FILE:-${BACKUP_DR_RUNTIME_DIR:-.runtime}/backup-test-key}"

if [ "$ENVIRONMENT" = "production" ]; then
  echo "BACKUP_ENCRYPTED_PRODUCE: FAIL refusing_production_environment"
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
./scripts/setup_backup_dr_test_key.sh >/dev/null || { echo "BACKUP_ENCRYPTED_PRODUCE: FAIL key_setup"; exit 1; }

ts=$(date -u +"%Y%m%dT%H%M%SZ")
backup_key="backup-dr-${ENVIRONMENT}-${ts}"
dump_path="$RUNTIME_DIR/${backup_key}.dump"
enc_path="$RUNTIME_DIR/${backup_key}.enc"

# 1. pg_dump (custom format) from the postgres container -> host file --------
echo "step=pg_dump db=$PG_DB"
$COMPOSE exec -T "$PG_SERVICE" pg_dump -U "$PG_USER" -Fc --no-owner --no-privileges "$PG_DB" \
  > "$dump_path" 2>/tmp/bdr_pgdump.log
if [ ! -s "$dump_path" ]; then
  tail -5 /tmp/bdr_pgdump.log 2>/dev/null || true
  echo "BACKUP_ENCRYPTED_PRODUCE: FAIL pg_dump_empty"
  exit 1
fi

# 2. encrypt (key piped via env into openssl; never on disk / argv) ----------
echo "step=encrypt"
BDR_KEY=$(cat "$KEY_FILE")
export BDR_KEY
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BDR_KEY \
  -in "$dump_path" -out "$enc_path" 2>/dev/null
enc_rc=$?
unset BDR_KEY
if [ "$enc_rc" -ne 0 ] || [ ! -s "$enc_path" ]; then
  echo "BACKUP_ENCRYPTED_PRODUCE: FAIL encrypt_failed"
  exit 1
fi

# 3. checksums ---------------------------------------------------------------
plain_sum=$(sha256sum "$dump_path" | awk '{print $1}')
enc_sum=$(sha256sum "$enc_path" | awk '{print $1}')
enc_size=$(wc -c < "$enc_path" | tr -d '[:space:]')

# 4. schema / table / row counts (from the live test DB) ---------------------
mig_count=$($COMPOSE exec -T "$PG_SERVICE" psql -U "$PG_USER" -d "$PG_DB" -tAc \
  "SELECT count(*) FROM pg_tables WHERE schemaname='public';" 2>/dev/null | tr -d '[:space:]')
mig_count="${mig_count:-0}"
audit_rows=$($COMPOSE exec -T "$PG_SERVICE" psql -U "$PG_USER" -d "$PG_DB" -tAc \
  "SELECT count(*) FROM audit_logs;" 2>/dev/null | tr -d '[:space:]')
audit_rows="${audit_rows:-0}"
migrations_applied=$(ls migrations/*.sql 2>/dev/null | grep -vc '_down.sql' || echo 0)

# 5. facts JSON --------------------------------------------------------------
facts_path="$RUNTIME_DIR/facts.json"
"$PY" - "$facts_path" "$backup_key" "$PG_DB" "$ENVIRONMENT" "$dump_path" "$enc_path" \
  "$plain_sum" "$enc_sum" "$enc_size" "$migrations_applied" "$mig_count" "$audit_rows" <<'PY'
import json, sys
(_, facts_path, backup_key, db, env, dump_path, enc_path, plain_sum, enc_sum,
 enc_size, migrations_applied, table_count, audit_rows) = sys.argv
facts = {
    "backup_key": backup_key,
    "source_database": db,
    "environment": env,
    "artifact_path": dump_path,
    "encrypted_artifact_path": enc_path,
    "checksum_sha256": plain_sum,
    "encrypted_checksum_sha256": enc_sum,
    "size_bytes": int(enc_size or 0),
    "schema_migration_count": int(migrations_applied or 0),
    "table_count": int(table_count or 0),
    "row_count_summary": {"audit_logs": int(audit_rows or 0)},
    "migrations_dir": "migrations",
    "production_executed": False,
}
with open(facts_path, "w", encoding="utf-8") as fh:
    json.dump(facts, fh, indent=2, sort_keys=True)
print(f"facts_path={facts_path}")
PY

echo "backup_key=$backup_key"
echo "encrypted_artifact=$enc_path"
echo "checksum_sha256=$plain_sum"
echo "encrypted_checksum_sha256=$enc_sum"
echo "BACKUP_ENCRYPTED_PRODUCE: PASS"
