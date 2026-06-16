#!/usr/bin/env bash
# Stage 51 -- isolated restore drill (decrypt + restore into a throwaway DB).
#
# Delegates the heavy encrypted backup + isolated restore + integrity verify to
# the proven Stage 36 run_restore_drill.sh (which refuses primary/production
# targets), then maps its RESTORE_DRILL marker to this stage's marker.
#
# Asserts production_restore_performed=false (the drill only ever targets an
# aiagents_restore_drill_* database).
#
# Marker: BACKUP_RESTORE_DRILL_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

echo "### verify_backup_restore_drill"
if [ ! -f scripts/run_restore_drill.sh ]; then
  echo "BACKUP_RESTORE_DRILL_VERIFY: FAIL run_restore_drill_missing"
  exit 1
fi
if bash scripts/run_restore_drill.sh >/tmp/bdr_restore_drill.log 2>&1; then
  tail -6 /tmp/bdr_restore_drill.log
  if grep -q "RESTORE_DRILL: PASS" /tmp/bdr_restore_drill.log; then
    echo "production_restore_performed=false (isolated drill DB only)"
    echo "BACKUP_RESTORE_DRILL_VERIFY: PASS"
    exit 0
  fi
fi
tail -12 /tmp/bdr_restore_drill.log
echo "BACKUP_RESTORE_DRILL_VERIFY: FAIL"
exit 1
