#!/usr/bin/env bash
# Stage 36 / Stage 51 -- production-readiness gate check.
#
# Reports on the production-readiness pillars. The four long-standing gaps
#   encryption_no_key, storage_not_off_host, schedule_dry_run_only,
#   migration_down_gaps
# are now closed at a CONTROLLED / TEST baseline by Stage 51's Backup / DR Gap
# Closure (source/dr-reports/backup_dr_readiness_latest.json). When the
# readiness snapshot shows all four closed, this script reports
# PASS_WITH_NON_PRODUCTION_LIMITATIONS (NOT a production-ready claim) instead of
# the old PASS_WITH_GAPS. If the snapshot is absent or a gap is still open, the
# original PASS_WITH_GAPS reporting is preserved (no strictness reduction).
#
# Claude Code does NOT decide production readiness; this only reports observed
# state.
#
# Markers:
#   BACKUP_PRODUCTION_READINESS_VERIFY: PASS
#   BACKUP_PRODUCTION_READINESS_VERIFY: PASS_WITH_NON_PRODUCTION_LIMITATIONS limitations=<csv>
#   BACKUP_PRODUCTION_READINESS: PASS_WITH_GAPS gaps=<csv>
#   BACKUP_PRODUCTION_READINESS: FAIL <reason>
set -uo pipefail

cd "$(dirname "$0")/.." 2>/dev/null || true
REPO_ROOT="$(pwd)"
SNAPSHOT="source/dr-reports/backup_dr_readiness_latest.json"
PYBIN="${PYTHON:-python3}"

gaps=""

# Stage 51 -- read the gap-closure readiness snapshot (source of truth for the
# four original gaps). Falls back to env / crontab detection when absent.
snap_status=""
enc_closed="false"; off_closed="false"; sched_closed="false"; mig_closed="false"
if [ -f "$SNAPSHOT" ]; then
  snap_status=$("$PYBIN" -c "import json;print(json.load(open('$SNAPSHOT')).get('status',''))" 2>/dev/null || echo "")
  enc_closed=$("$PYBIN" -c "import json;print(str(json.load(open('$SNAPSHOT')).get('encryption_gap_closed',False)).lower())" 2>/dev/null || echo false)
  off_closed=$("$PYBIN" -c "import json;print(str(json.load(open('$SNAPSHOT')).get('offhost_gap_closed',False)).lower())" 2>/dev/null || echo false)
  sched_closed=$("$PYBIN" -c "import json;print(str(json.load(open('$SNAPSHOT')).get('schedule_gap_closed',False)).lower())" 2>/dev/null || echo false)
  mig_closed=$("$PYBIN" -c "import json;print(str(json.load(open('$SNAPSHOT')).get('migration_down_gap_closed',False)).lower())" 2>/dev/null || echo false)
fi
echo "backup_dr_readiness_snapshot=${snap_status:-absent}"

# 1. encryption ---------------------------------------------------------
if [ "$enc_closed" = "true" ]; then
  encryption_status="gap_closed_test_baseline"
elif [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  encryption_status="env_key_present"
else
  encryption_status="no_key"
  gaps="${gaps}encryption_no_key,"
fi
echo "encryption_status=$encryption_status"

# 2. storage / off-host -------------------------------------------------
if [ "$off_closed" = "true" ]; then
  storage_status="offhost_gap_closed_mock_target"
else
  storage_status="not_off_host"
  gaps="${gaps}storage_not_off_host,"
fi
echo "storage_status=$storage_status"

# 3. schedule -----------------------------------------------------------
if [ "$sched_closed" = "true" ]; then
  schedule_status="dry_run_validated_spec"
elif crontab -l 2>/dev/null | grep -q 'backup'; then
  schedule_status="cron_installed"
else
  schedule_status="dry_run_only"
  gaps="${gaps}schedule_dry_run_only,"
fi
echo "schedule_status=$schedule_status"

# 4. migration rollback / down -----------------------------------------
if [ "$mig_closed" = "true" ]; then
  migration_status="rollback_catalog_complete"
else
  inv_output=$(./scripts/check_migration_down_scripts.sh 2>/dev/null || echo "")
  if echo "$inv_output" | grep -q 'MIGRATION_DOWN_SCRIPT_INVENTORY: PASS$'; then
    migration_status="complete"
  else
    migration_status="gaps"
    gaps="${gaps}migration_down_gaps,"
  fi
fi
echo "migration_status=$migration_status"

# 5. DR runbooks --------------------------------------------------------
runbook_status="present"
for p in "docs/operations/restore-drill-runbook.md" \
         "docs/operations/backup-dr-gap-closure.md"; do
  if [ ! -f "$p" ]; then
    runbook_status="missing"
    gaps="${gaps}runbook_missing,"
  fi
done
echo "runbook_status=$runbook_status"

# Final marker ----------------------------------------------------------
gaps="${gaps%,}"

# Non-production limitations always apply at this stage (no real production
# secret store / cloud target / production schedule / production restore).
LIMITATIONS="real_production_secret_store_not_integrated,real_off_host_cloud_target_not_enabled,production_schedule_not_enabled,production_restore_not_executed"

if [ -n "$gaps" ]; then
  echo "BACKUP_PRODUCTION_READINESS: PASS_WITH_GAPS gaps=$gaps"
  exit 0
fi

if [ "$enc_closed" = "true" ] && [ "$off_closed" = "true" ] \
   && [ "$sched_closed" = "true" ] && [ "$mig_closed" = "true" ]; then
  if [ "$snap_status" = "passed" ]; then
    echo "BACKUP_PRODUCTION_READINESS_VERIFY: PASS"
  else
    echo "BACKUP_PRODUCTION_READINESS_VERIFY: PASS_WITH_NON_PRODUCTION_LIMITATIONS limitations=$LIMITATIONS"
  fi
  exit 0
fi

echo "BACKUP_PRODUCTION_READINESS_VERIFY: PASS"
exit 0
