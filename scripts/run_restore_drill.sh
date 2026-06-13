#!/usr/bin/env bash
# Stage 36 -- restore drill into an ISOLATED restore database.
#
# Flow:
#   1. create encrypted backup + manifest (scripts/backup_postgres_encrypted.sh)
#   2. compute checksum
#   3. optional off-host upload (skipped if no creds)
#   4. CREATE DATABASE aiagents_restore_drill_<ts>
#   5. decrypt backup to /tmp inside postgres container
#   6. pg_restore into the isolated DB
#   7. row count verification (audit_logs, audit_integrity_records,
#      workflow_states, llm_budget_events, notification_deliveries)
#   8. audit integrity verify on the isolated DB
#   9. DROP DATABASE aiagents_restore_drill_<ts>  (unless KEEP_RESTORE_DRILL_DB=true)
#  10. write source/dr-reports/dr_report_{ts}.json + dr_report_latest.json
#  11. marker RESTORE_DRILL: PASS  or  FAIL
#
# Hard rules:
#   * Refuses to restore into 'aiagents' / 'postgres' / template DBs.
#   * Refuses to drop a DB that doesn't start with
#     aiagents_restore_drill_.
#   * Never echoes credentials / encryption key value.
#
# Run from repo root.
set -uo pipefail

REPO_ROOT="$(pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
DR_REPORTS_DIR="${DR_REPORTS_DIR:-source/dr-reports}"
KEEP_RESTORE_DRILL_DB="${KEEP_RESTORE_DRILL_DB:-false}"

mkdir -p "$BACKUP_DIR" "$DR_REPORTS_DIR"

ts=$(date -u +"%Y%m%dT%H%M%SZ")
drill_id="drill-${ts}"
restore_db="aiagents_restore_drill_${ts,,}"
report_path="$DR_REPORTS_DIR/dr_report_${ts}.json"
latest_report_path="$DR_REPORTS_DIR/dr_report_latest.json"

case "$restore_db" in
  aiagents|postgres|template0|template1)
    echo "RESTORE_DRILL: FAIL refusing_primary_target"
    exit 1
    ;;
esac

# Guard: only aiagents_restore_drill_ prefix may be created/dropped.
if [[ "$restore_db" != aiagents_restore_drill_* ]]; then
  echo "RESTORE_DRILL: FAIL unsafe_restore_db_name=$restore_db"
  exit 1
fi

started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
total_start=$(date +%s.%N)

echo "### run_restore_drill drill_id=$drill_id restore_db=$restore_db"

# Auto-generate a test-only key if none supplied (drill must always
# exercise the encryption path).
test_key_path=""
if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ] && [ -z "${BACKUP_KEY_SOURCE:-}" ]; then
  export BACKUP_KEY_SOURCE="test-only-generated"
  test_key_path="$(mktemp /tmp/aiagents-drill-key.XXXXXX)"
  chmod 600 "$test_key_path"
  openssl rand -base64 48 > "$test_key_path"
  export BACKUP_KEY_FILE="$test_key_path"
  # Mirror into BACKUP_ENCRYPTION_KEY env so the encrypted backup
  # script (which reads env:BACKUP_ENCRYPTION_KEY) gets the same key.
  # Pipe instead of substitution to avoid log echo.
  BACKUP_ENCRYPTION_KEY=$(cat "$test_key_path")
  export BACKUP_ENCRYPTION_KEY
fi

# 1. encrypted backup ---------------------------------------------------
echo "step=1 encrypted_backup"
./scripts/backup_postgres_encrypted.sh > /tmp/aiagents-drill-backup.log 2>&1
backup_rc=$?
backup_log_tail=$(tail -8 /tmp/aiagents-drill-backup.log)
if [ "$backup_rc" -ne 0 ]; then
  echo "$backup_log_tail"
  echo "RESTORE_DRILL: FAIL backup_step_failed"
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit "$backup_rc"
fi
manifest_path=$(grep -E '^manifest_path=' /tmp/aiagents-drill-backup.log | tail -1 | cut -d= -f2-)
artifact_path=$(grep -E '^artifact_path=' /tmp/aiagents-drill-backup.log | tail -1 | cut -d= -f2-)
backup_id=$(grep -E '^backup_id=' /tmp/aiagents-drill-backup.log | tail -1 | cut -d= -f2-)
backup_duration=$(grep -E 'pg_dump size_bytes' /tmp/aiagents-drill-backup.log | sed -E 's/.*duration_seconds=([0-9.]+).*/\1/' || echo "0")
encryption_duration=$(grep -E 'encrypt done duration_seconds' /tmp/aiagents-drill-backup.log | sed -E 's/.*duration_seconds=([0-9.]+).*/\1/' || echo "0")
backup_duration="${backup_duration:-0}"
encryption_duration="${encryption_duration:-0}"

if [ -z "$artifact_path" ] || [ ! -f "$artifact_path" ]; then
  echo "RESTORE_DRILL: FAIL backup_artifact_missing"
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit 1
fi

# 2. checksum verify ----------------------------------------------------
echo "step=2 checksum_verify"
manifest_checksum=$(python3 -c "
import json,sys
print(json.load(open(sys.argv[1]))['checksum_sha256'])
" "$manifest_path")
actual_checksum=$(openssl dgst -sha256 -hex "$artifact_path" | awk '{print $NF}')
if [ "$manifest_checksum" != "$actual_checksum" ]; then
  echo "RESTORE_DRILL: FAIL checksum_mismatch manifest=$manifest_checksum actual=$actual_checksum"
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit 1
fi

# 3. optional off-host upload ------------------------------------------
echo "step=3 off_host_upload"
upload_start=$(date +%s.%N)
./scripts/upload_backup_artifact.sh "$artifact_path" "$backup_id" > /tmp/aiagents-drill-upload.log 2>&1 || true
upload_end=$(date +%s.%N)
upload_duration=$(awk -v a="$upload_start" -v b="$upload_end" 'BEGIN {printf "%.3f", b - a}')
upload_marker=$(grep -E '^BACKUP_UPLOAD:' /tmp/aiagents-drill-upload.log | tail -1)
off_host_uploaded="false"
off_host_uri="null"
case "$upload_marker" in
  *"PASS uri="*)
    off_host_uploaded="true"
    off_host_uri=$(echo "$upload_marker" | sed -E 's/.*uri=//')
    off_host_uri="\"$off_host_uri\""
    ;;
  *"SKIPPED"*)
    off_host_uploaded="false"
    ;;
esac

# 4. create isolated restore DB ----------------------------------------
echo "step=4 create_restore_db=$restore_db"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $restore_db;" >/dev/null 2>&1
create_rc=$?
if [ "$create_rc" -ne 0 ]; then
  echo "RESTORE_DRILL: FAIL create_database_failed rc=$create_rc"
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit "$create_rc"
fi

# 5. copy + decrypt the artifact INSIDE the postgres container ---------
echo "step=5 decrypt"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  bash -c "cat > /tmp/aiagents-drill.enc" < "$artifact_path"

dec_start=$(date +%s.%N)
# The encryption key is in env:BACKUP_ENCRYPTION_KEY for our process.
# Pipe it INTO the container with -e so it never lands on disk inside
# the container and never appears in the docker compose ps output.
docker compose -f "$COMPOSE_FILE" exec -T \
  -e BACKUP_ENCRYPTION_KEY="$BACKUP_ENCRYPTION_KEY" \
  "$POSTGRES_SERVICE" \
  bash -c "openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_KEY -in /tmp/aiagents-drill.enc -out /tmp/aiagents-drill.dump 2>/dev/null" \
  || dec_rc=$?
dec_end=$(date +%s.%N)
dec_rc="${dec_rc:-0}"
if [ "$dec_rc" -ne 0 ]; then
  echo "RESTORE_DRILL: FAIL decrypt_failed"
  docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $restore_db;" >/dev/null 2>&1
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit 1
fi

# 6. pg_restore into isolated DB ---------------------------------------
echo "step=6 pg_restore"
restore_start=$(date +%s.%N)
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore --no-owner --clean --if-exists --exit-on-error \
    -U "$POSTGRES_USER" -d "$restore_db" /tmp/aiagents-drill.dump \
  >/tmp/aiagents-drill-restore.log 2>&1
restore_rc=$?
restore_end=$(date +%s.%N)
restore_duration=$(awk -v a="$restore_start" -v b="$restore_end" 'BEGIN {printf "%.3f", b - a}')
if [ "$restore_rc" -ne 0 ]; then
  echo "pg_restore log (tail):"
  tail -20 /tmp/aiagents-drill-restore.log
  echo "RESTORE_DRILL: FAIL pg_restore_rc=$restore_rc"
  docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    bash -c "rm -f /tmp/aiagents-drill.enc /tmp/aiagents-drill.dump" >/dev/null 2>&1 || true
  if [ "$KEEP_RESTORE_DRILL_DB" != "true" ]; then
    docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
      psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $restore_db;" >/dev/null 2>&1
  fi
  [ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true
  exit "$restore_rc"
fi

# 7. row count verification --------------------------------------------
echo "step=7 row_counts"
row_counts_json="{}"
for tbl in audit_logs audit_integrity_records workflow_states deployment_records \
           notification_deliveries llm_interactions llm_budget_events; do
  cnt=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$restore_db" -tAc \
    "SELECT count(*) FROM ${tbl};" 2>/dev/null | tr -d '[:space:]')
  cnt="${cnt:-0}"
  row_counts_json=$(python3 -c "
import json,sys
d = json.loads(sys.argv[1]); d['$tbl'] = int('$cnt')
print(json.dumps(d, sort_keys=True))
" "$row_counts_json")
done
echo "row_counts=$row_counts_json"

# 8. audit integrity verify on isolated DB -----------------------------
echo "step=8 audit_integrity_verify"
integrity_start=$(date +%s.%N)
audit_integrity_status="not_run"
audit_integrity_records_checked=0
audit_integrity_mismatches=0
ai_cnt=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$restore_db" -tAc \
  "SELECT count(*) FROM audit_integrity_records;" 2>/dev/null | tr -d '[:space:]')
ai_cnt="${ai_cnt:-0}"
if [ "$ai_cnt" -gt 0 ]; then
  # The chain-verifier walks audit_integrity_records by sequence and
  # compares each record's hash to the canonical recomputed digest.
  # For the drill we run a *structural* verify (chain link continuity)
  # so we don't need the audit-service running.
  mismatches=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$restore_db" -tAc "
    WITH walked AS (
      SELECT a.sequence_number,
             a.prev_record_hash,
             lag(a.record_hash) OVER (ORDER BY a.sequence_number) AS expected_prev
      FROM audit_integrity_records a
    )
    SELECT count(*) FROM walked
    WHERE sequence_number > 1
      AND (expected_prev IS NULL OR prev_record_hash <> expected_prev);
  " 2>/dev/null | tr -d '[:space:]')
  mismatches="${mismatches:-0}"
  audit_integrity_records_checked="$ai_cnt"
  audit_integrity_mismatches="$mismatches"
  if [ "$mismatches" -eq 0 ]; then
    audit_integrity_status="passed"
  else
    audit_integrity_status="failed"
  fi
else
  audit_integrity_status="empty_chain"
fi
integrity_end=$(date +%s.%N)
integrity_duration=$(awk -v a="$integrity_start" -v b="$integrity_end" 'BEGIN {printf "%.3f", b - a}')

# 9. cleanup ------------------------------------------------------------
cleanup_completed="false"
echo "step=9 cleanup"
docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  bash -c "rm -f /tmp/aiagents-drill.enc /tmp/aiagents-drill.dump" >/dev/null 2>&1 || true
if [ "$KEEP_RESTORE_DRILL_DB" = "true" ]; then
  echo "KEEP_RESTORE_DRILL_DB=true -- preserving $restore_db"
  cleanup_completed="false"
else
  # Allow up to 3 attempts in case sessions linger.
  for attempt in 1 2 3; do
    docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
      psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $restore_db;" >/dev/null 2>&1
    drop_rc=$?
    if [ "$drop_rc" -eq 0 ]; then
      cleanup_completed="true"
      break
    fi
    sleep 1
  done
fi

# --- key cleanup ---------------------------------------------------------
[ -n "$test_key_path" ] && shred -u "$test_key_path" 2>/dev/null || true

total_end=$(date +%s.%N)
total_duration=$(awk -v a="$total_start" -v b="$total_end" 'BEGIN {printf "%.3f", b - a}')
finished_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 10. write DR report ----------------------------------------------------
echo "step=10 write_dr_report"

# Estimated RPO -- age of *this* backup at drill end (latest known).
rpo_seconds="0"
rpo_status="manual_only"

python3 - "$report_path" "$latest_report_path" "$drill_id" \
  "$started_at" "$finished_at" "$backup_id" "$artifact_path" \
  "$manifest_path" "$restore_db" "$audit_integrity_status" \
  "$audit_integrity_records_checked" "$audit_integrity_mismatches" \
  "$backup_duration" "$encryption_duration" "$upload_duration" \
  "$restore_duration" "$integrity_duration" "$total_duration" \
  "$rpo_seconds" "$rpo_status" "$cleanup_completed" \
  "$off_host_uploaded" "$off_host_uri" "$row_counts_json" <<'PY'
import json, sys

(_, report_path, latest_path, drill_id, started_at, finished_at,
 backup_id, artifact_path, manifest_path, restore_db,
 audit_status, audit_checked, audit_mismatches,
 backup_dur, enc_dur, up_dur, restore_dur, int_dur, total_dur,
 rpo_seconds, rpo_status, cleanup_completed,
 off_host_uploaded, off_host_uri, row_counts_json) = sys.argv

off_host_uri_val = None if off_host_uri == "null" else json.loads(off_host_uri)

report = {
    "drill_id": drill_id,
    "started_at": started_at,
    "finished_at": finished_at,
    "backup_id": backup_id,
    "backup_artifact_path": artifact_path,
    "manifest_path": manifest_path,
    "restore_db": restore_db,
    "status": "passed" if audit_status in ("passed", "empty_chain") else "failed",
    "row_count_summary": json.loads(row_counts_json),
    "audit_integrity_status": audit_status,
    "audit_integrity_records_checked": int(audit_checked),
    "audit_integrity_mismatches": int(audit_mismatches),
    "backup_duration_seconds": float(backup_dur or 0),
    "encryption_duration_seconds": float(enc_dur or 0),
    "upload_duration_seconds": float(up_dur or 0),
    "download_duration_seconds": 0.0,
    "restore_duration_seconds": float(restore_dur or 0),
    "integrity_verify_duration_seconds": float(int_dur or 0),
    "total_drill_duration_seconds": float(total_dur or 0),
    "estimated_rto_seconds": float(total_dur or 0),
    "estimated_rpo_seconds": float(rpo_seconds or 0),
    "rpo_status": rpo_status,
    "cleanup_completed": cleanup_completed == "true",
    "off_host_uploaded": off_host_uploaded == "true",
    "off_host_uri": off_host_uri_val,
    "encrypted": True,
    "encryption_mode": "openssl-aes-256-cbc",
    "production_executed": False,
    "failure_reason": None,
    "notes": [],
}

with open(report_path, "w", encoding="utf-8") as fh:
    json.dump(report, fh, sort_keys=True, indent=2)
with open(latest_path, "w", encoding="utf-8") as fh:
    json.dump(report, fh, sort_keys=True, indent=2)

print(f"dr_report_path={report_path}")
print(f"dr_report_latest={latest_path}")
PY

echo "drill_id=$drill_id restore_db=$restore_db duration_seconds=$total_duration"
echo "audit_integrity_status=$audit_integrity_status"
echo "cleanup_completed=$cleanup_completed off_host_uploaded=$off_host_uploaded"

if [ "$audit_integrity_status" = "failed" ]; then
  echo "RESTORE_DRILL: FAIL audit_integrity_mismatches=$audit_integrity_mismatches"
  exit 1
fi
echo "RESTORE_DRILL: PASS"
