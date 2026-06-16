#!/usr/bin/env bash
# Stage 51 -- backup retention policy dry-run.
#
# Builds a retention policy + computes a dry-run cleanup report. Asserts
# delete_enabled=false and actual_delete_count=0 (no deletion performed).
#
# Marker: BACKUP_RETENTION_POLICY_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
PY="${PYTHON:-python3}"

echo "### verify_backup_retention_policy"
result=$("$PY" - <<'PY'
import json
from shared.sdk.backup_dr.retention_policy import (
    build_retention_policy, compute_retention_dry_run, retention_configured,
)
p = build_retention_policy()
# simulate more backups than keep_last to exercise candidate detection
backups = [{"backup_key": f"b{i}", "created_at": f"2026-06-{i:02d}"} for i in range(1, 12)]
report = compute_retention_dry_run(p, backups)
print(json.dumps({
    "configured": retention_configured(p),
    "delete_enabled": report["delete_enabled"],
    "actual_delete_count": report["actual_delete_count"],
    "candidate_delete_count": report["candidate_delete_count"],
}))
PY
)
echo "$result"
ok=$("$PY" -c "import json;d=json.loads('''$result''');print(d['configured'] and not d['delete_enabled'] and d['actual_delete_count']==0)" 2>/dev/null)
if [ "$ok" = "True" ]; then echo "BACKUP_RETENTION_POLICY_VERIFY: PASS"; exit 0; fi
echo "BACKUP_RETENTION_POLICY_VERIFY: FAIL"; exit 1
