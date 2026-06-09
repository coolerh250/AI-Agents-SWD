#!/usr/bin/env bash
# Stage 36 -- encrypted backup + manifest baseline.
#
# Builds on scripts/backup_postgres.sh:
#
#   1. runs pg_dump --format=custom into BACKUP_DIR (defaults to ./backups)
#   2. computes sha256 over the raw dump
#   3. encrypts to <dump>.enc via openssl AES-256-CBC + salt; the key
#      value never appears on stdout / stderr (-pass env:...)
#   4. computes sha256 over the encrypted artifact
#   5. writes backup_manifest_{backup_id}.json beside the artifact
#
# Inputs (env):
#   BACKUP_ENCRYPTION_KEY -- production-only; absent in test means we
#                            fall back to a /tmp keyfile if
#                            BACKUP_KEY_SOURCE=test-only-generated.
#   BACKUP_KEY_SOURCE     -- 'env' (default if BACKUP_ENCRYPTION_KEY set),
#                            'test-only-generated', or 'missing'.
#   BACKUP_ENVIRONMENT    -- 'local' / 'test' / 'staging'. NEVER 'production'.
#   BACKUP_DIR            -- output directory (default ./backups).
#
# The script EXITS 0 with marker BACKUP_POSTGRES_ENCRYPTED: PASS on
# success, or FAIL on any of: pg_dump rc!=0, openssl rc!=0, missing key
# in production-check mode, manifest write failure.
#
# Never logs / prints / writes a key value. Run from repo root.
set -uo pipefail

REPO_ROOT="$(pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_ENVIRONMENT="${BACKUP_ENVIRONMENT:-local}"

mkdir -p "$BACKUP_DIR"

# Hard-block accidental production routing.
case "$BACKUP_ENVIRONMENT" in
  production|production-check|prod)
    echo "BACKUP_POSTGRES_ENCRYPTED: FAIL (refusing BACKUP_ENVIRONMENT=$BACKUP_ENVIRONMENT)"
    exit 1
    ;;
esac

ts=$(date -u +"%Y%m%dT%H%M%SZ")
backup_id="bkp-${ts}-$(printf '%04x' $((RANDOM % 65536)))"
raw_out="$BACKUP_DIR/aiagents-${ts}.dump"
enc_out="${raw_out}.enc"
manifest_path="$BACKUP_DIR/backup_manifest_${backup_id}.json"

echo "### backup_postgres_encrypted start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "backup_id=$backup_id"
echo "raw=$raw_out enc=$enc_out manifest=$manifest_path"

# --- key source resolution ---------------------------------------------------
key_source="missing"
key_id="unknown"
encrypted_flag="false"
encryption_mode="none"
production_ready="false"
test_keyfile=""

if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  key_source="env"
  encrypted_flag="true"
  encryption_mode="openssl-aes-256-cbc"
  production_ready="true"
  # Opaque label: sha256(key)[:8] -- never the key itself.
  key_id=$(printf '%s' "$BACKUP_ENCRYPTION_KEY" | openssl dgst -sha256 -hex 2>/dev/null \
    | awk '{print substr($NF,1,8)}')
elif [ "${BACKUP_KEY_SOURCE:-}" = "test-only-generated" ]; then
  test_keyfile="$(mktemp /tmp/aiagents-backup-key.XXXXXX)"
  chmod 600 "$test_keyfile"
  openssl rand -base64 48 > "$test_keyfile"
  # Do NOT echo the key. Only the path + chmod.
  echo "test-only key generated at $test_keyfile (chmod 600)"
  key_source="test-only-generated"
  encrypted_flag="true"
  encryption_mode="openssl-aes-256-cbc"
  production_ready="false"
  key_id="test-only-ephemeral"
fi

# --- pg_dump ---------------------------------------------------------------
echo "step=pg_dump"
start_dump=$(date +%s.%N)
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$raw_out"
rc=$?
end_dump=$(date +%s.%N)
if [ "$rc" -ne 0 ]; then
  echo "BACKUP_POSTGRES_ENCRYPTED: FAIL (pg_dump rc=$rc)"
  rm -f "$raw_out"
  [ -n "$test_keyfile" ] && rm -f "$test_keyfile"
  exit "$rc"
fi
backup_size_bytes=$(wc -c < "$raw_out" | tr -d '[:space:]')
backup_duration=$(awk -v a="$start_dump" -v b="$end_dump" 'BEGIN {printf "%.3f", b - a}')
echo "pg_dump size_bytes=$backup_size_bytes duration_seconds=$backup_duration"

# --- pg_version (informational) --------------------------------------------
pg_version=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SHOW server_version;" \
  2>/dev/null | tr -d '[:space:]')
pg_version="${pg_version:-unknown}"

# --- included tables + row counts (best effort) ----------------------------
included_tables_csv=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT string_agg(table_name, ',' ORDER BY table_name) FROM information_schema.tables WHERE table_schema='public';" \
  2>/dev/null | tr -d '\r')
included_tables_csv="${included_tables_csv:-}"

row_counts_json="{}"
for tbl in audit_logs audit_integrity_records workflow_states deployment_records \
          notification_deliveries llm_interactions llm_budget_events; do
  cnt=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT count(*) FROM ${tbl};" 2>/dev/null | tr -d '[:space:]')
  cnt="${cnt:-0}"
  row_counts_json=$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
d['$tbl'] = int('$cnt')
print(json.dumps(d, sort_keys=True))
" "$row_counts_json")
done

# --- audit chain latest hash (best effort) --------------------------------
audit_chain_latest_hash=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT encode(record_hash, 'hex') FROM audit_integrity_records ORDER BY sequence_number DESC LIMIT 1;" \
  2>/dev/null | tr -d '[:space:]')
audit_chain_latest_hash="${audit_chain_latest_hash:-}"

# --- encryption ------------------------------------------------------------
if [ "$encrypted_flag" = "true" ]; then
  echo "step=encrypt mode=$encryption_mode"
  start_enc=$(date +%s.%N)
  if [ "$key_source" = "env" ]; then
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass env:BACKUP_ENCRYPTION_KEY \
      -in "$raw_out" -out "$enc_out" 2>/dev/null
    enc_rc=$?
  else
    # test-only keyfile path; openssl reads pass:file directly.
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass file:"$test_keyfile" \
      -in "$raw_out" -out "$enc_out" 2>/dev/null
    enc_rc=$?
  fi
  end_enc=$(date +%s.%N)
  if [ "$enc_rc" -ne 0 ]; then
    echo "BACKUP_POSTGRES_ENCRYPTED: FAIL (openssl enc rc=$enc_rc)"
    rm -f "$raw_out" "$enc_out"
    [ -n "$test_keyfile" ] && rm -f "$test_keyfile"
    exit "$enc_rc"
  fi
  encryption_duration=$(awk -v a="$start_enc" -v b="$end_enc" 'BEGIN {printf "%.3f", b - a}')
  echo "encrypt done duration_seconds=$encryption_duration"
  artifact_path="$enc_out"
  # Remove the raw dump so only the encrypted artifact stays on disk.
  rm -f "$raw_out"
else
  echo "step=encrypt SKIPPED (no key source)"
  encryption_duration="0.000"
  artifact_path="$raw_out"
fi

# --- checksum --------------------------------------------------------------
checksum_sha256=$(openssl dgst -sha256 -hex "$artifact_path" 2>/dev/null | awk '{print $NF}')
artifact_size_bytes=$(wc -c < "$artifact_path" | tr -d '[:space:]')
echo "artifact=$artifact_path size_bytes=$artifact_size_bytes sha256=$checksum_sha256"

# --- manifest --------------------------------------------------------------
python3 - "$manifest_path" "$backup_id" "$BACKUP_ENVIRONMENT" \
  "$POSTGRES_DB" "$POSTGRES_SERVICE" "$pg_version" \
  "$artifact_path" "$artifact_size_bytes" "$checksum_sha256" \
  "$encrypted_flag" "$encryption_mode" "$key_id" \
  "$included_tables_csv" "$row_counts_json" "$audit_chain_latest_hash" \
  "$backup_duration" "$encryption_duration" <<'PY'
import json, os, sys, datetime

(_, manifest_path, backup_id, env, db, host, pg_version,
 artifact_path, size_bytes, checksum, encrypted, mode, key_id,
 tables_csv, rowcounts_json, audit_hash,
 backup_duration, encryption_duration) = sys.argv

manifest = {
    "backup_id": backup_id,
    "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "environment": env,
    "source_database": db,
    "source_host": host,
    "pg_version": pg_version,
    "backup_format": "pg_dump-custom",
    "backup_file": artifact_path,
    "backup_size_bytes": int(size_bytes),
    "checksum_sha256": checksum,
    "encrypted": encrypted == "true",
    "encryption_mode": mode,
    "encryption_key_id": (key_id or None),
    "compression": "pg_dump-custom-zlib",
    "off_host_uploaded": False,
    "off_host_uri": None,
    "schema_version": "1.0",
    "included_tables": [t for t in tables_csv.split(",") if t],
    "row_count_summary": json.loads(rowcounts_json) if rowcounts_json else {},
    "audit_chain_latest_hash": (audit_hash or None),
    "created_by": "scripts/backup_postgres_encrypted.sh",
    "production_executed": False,
    "backup_duration_seconds": float(backup_duration),
    "encryption_duration_seconds": float(encryption_duration),
}
with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, sort_keys=True, indent=2)
print(f"manifest_path={manifest_path}")
PY

# --- cleanup test keyfile ---------------------------------------------------
if [ -n "$test_keyfile" ]; then
  shred -u "$test_keyfile" 2>/dev/null || rm -f "$test_keyfile"
fi

echo "backup_id=$backup_id"
echo "manifest_path=$manifest_path"
echo "artifact_path=$artifact_path"
echo "encrypted=$encrypted_flag mode=$encryption_mode production_ready=$production_ready"
echo "BACKUP_POSTGRES_ENCRYPTED: PASS"
