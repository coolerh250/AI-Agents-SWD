#!/usr/bin/env bash
# Stage 51 -- backup schedule dry-run validation.
#
# Builds cron / systemd / k8s schedule specs, asserts dry_run_validated=true and
# production_schedule_enabled=false (no real schedule installed).
#
# Marker: BACKUP_SCHEDULE_DRY_RUN_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
PY="${PYTHON:-python3}"

echo "### verify_backup_schedule_dry_run"
result=$("$PY" - <<'PY'
import json
from shared.sdk.backup_dr.schedule_builder import (
    build_cron_spec, build_systemd_timer_spec, build_kubernetes_cronjob_spec, schedule_gap_closed,
)
specs = [build_cron_spec(), build_systemd_timer_spec(), build_kubernetes_cronjob_spec()]
ok = all(schedule_gap_closed(s) for s in specs)
prod = any(s.production_schedule_enabled or s.enabled for s in specs)
print(json.dumps({"all_validated": ok, "any_production": prod}))
PY
)
echo "$result"
ok=$("$PY" -c "import json;d=json.loads('''$result''');print(d['all_validated'] and not d['any_production'])" 2>/dev/null)
if [ "$ok" = "True" ]; then echo "BACKUP_SCHEDULE_DRY_RUN_VERIFY: PASS"; exit 0; fi
echo "BACKUP_SCHEDULE_DRY_RUN_VERIFY: FAIL"; exit 1
