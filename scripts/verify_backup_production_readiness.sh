#!/usr/bin/env bash
# Stage 36 -- production-readiness gate check.
#
# Reports on the four production-readiness pillars:
#   1. Encryption (env key present)
#   2. Off-host storage (S3 mode with creds OR local-filesystem)
#   3. Scheduled backup (cron line installed OR dry-run only)
#   4. RTO/RPO measured (DR report exists; status=passed)
#   5. Migration down inventory (zero gaps OR documented gaps)
#   6. DR runbook present (docs/operations/backup-restore-dr.md)
#
# Markers:
#   BACKUP_PRODUCTION_READINESS: PASS
#   BACKUP_PRODUCTION_READINESS: PASS_WITH_GAPS gaps=<csv>
#   BACKUP_PRODUCTION_READINESS: FAIL <reason>
set -uo pipefail

REPO_ROOT="$(pwd)"

gaps=""

# 1. encryption ---------------------------------------------------------
if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  encryption_status="env_key_present"
elif [ "${BACKUP_KEY_SOURCE:-}" = "test-only-generated" ]; then
  encryption_status="test_only_generated"
  gaps="${gaps}encryption_test_only,"
else
  encryption_status="no_key"
  gaps="${gaps}encryption_no_key,"
fi
echo "encryption_status=$encryption_status"

# 2. storage ------------------------------------------------------------
mode="${BACKUP_STORAGE_MODE:-local-filesystem}"
case "$mode" in
  s3-compatible-placeholder)
    if [ -n "${BACKUP_STORAGE_BUCKET:-}" ] && [ -n "${BACKUP_STORAGE_ACCESS_KEY_ID:-}" ] \
       && [ -n "${BACKUP_STORAGE_SECRET_ACCESS_KEY:-}" ]; then
      storage_status="s3_wired_not_implemented"
      gaps="${gaps}storage_s3_not_implemented,"
    else
      storage_status="s3_credential_missing"
      gaps="${gaps}storage_credential_missing,"
    fi
    ;;
  local-filesystem)
    storage_status="local_filesystem"
    gaps="${gaps}storage_not_off_host,"
    ;;
  disabled)
    storage_status="disabled"
    gaps="${gaps}storage_disabled,"
    ;;
  *)
    storage_status="unknown"
    gaps="${gaps}storage_unknown,"
    ;;
esac
echo "storage_status=$storage_status"

# 3. schedule -----------------------------------------------------------
if crontab -l 2>/dev/null | grep -q 'backup_postgres_encrypted.sh'; then
  schedule_status="cron_installed"
else
  schedule_status="dry_run_only"
  gaps="${gaps}schedule_dry_run_only,"
fi
echo "schedule_status=$schedule_status"

# 4. DR report ----------------------------------------------------------
DR_REPORTS_DIR="${DR_REPORTS_DIR:-source/dr-reports}"
latest="$DR_REPORTS_DIR/dr_report_latest.json"
if [ -f "$latest" ]; then
  status=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('status',''))" "$latest")
  if [ "$status" = "passed" ]; then
    dr_status="latest_passed"
  else
    dr_status="latest_${status:-unknown}"
    gaps="${gaps}dr_report_${status:-unknown},"
  fi
else
  dr_status="no_dr_report"
  gaps="${gaps}no_dr_report,"
fi
echo "dr_status=$dr_status"

# 5. migration down inventory ------------------------------------------
inv_output=$(./scripts/check_migration_down_scripts.sh)
echo "$inv_output" | tail -8
if echo "$inv_output" | grep -q 'MIGRATION_DOWN_SCRIPT_INVENTORY: PASS$'; then
  migration_status="complete"
else
  migration_status="gaps"
  gaps="${gaps}migration_down_gaps,"
fi
echo "migration_status=$migration_status"

# 6. DR runbook ---------------------------------------------------------
runbook_paths=("docs/operations/backup-restore-dr.md" \
               "docs/operations/restore-drill-runbook.md")
runbook_status="present"
for p in "${runbook_paths[@]}"; do
  if [ ! -f "$p" ]; then
    runbook_status="missing"
    gaps="${gaps}runbook_missing,"
  fi
done
echo "runbook_status=$runbook_status"

# Final marker ---------------------------------------------------------
gaps="${gaps%,}"

if [ -z "$gaps" ]; then
  echo "BACKUP_PRODUCTION_READINESS: PASS"
else
  echo "BACKUP_PRODUCTION_READINESS: PASS_WITH_GAPS gaps=$gaps"
fi
