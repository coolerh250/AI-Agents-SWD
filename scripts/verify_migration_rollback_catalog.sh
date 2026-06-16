#!/usr/bin/env bash
# Stage 51 -- migration rollback catalog completeness.
#
# Scans migrations/, classifies every migration (reversible / forward_only /
# manual_rollback_required), asserts unknown_count=0 and that forward-only /
# manual rollback migrations carry notes.
#
# Marker: MIGRATION_ROLLBACK_CATALOG_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
PY="${PYTHON:-python3}"

echo "### verify_migration_rollback_catalog"
out=$("$PY" -m shared.sdk.backup_dr.cli migration-catalog 2>/tmp/bdr_catalog_err.log) || true
echo "$out"
if [ -z "$out" ]; then
  cat /tmp/bdr_catalog_err.log 2>/dev/null
  echo "MIGRATION_ROLLBACK_CATALOG_VERIFY: FAIL no_output"
  exit 1
fi
complete=$("$PY" -c "import json,sys;d=json.loads('''$out''');print(d.get('complete'))" 2>/dev/null)
unknown=$("$PY" -c "import json,sys;d=json.loads('''$out''');print(d.get('unknown'))" 2>/dev/null)
notes_ok=$("$PY" - <<'PY'
from shared.sdk.backup_dr.migration_catalog import build_migration_catalog
e = build_migration_catalog("migrations")
bad = [x.migration_file for x in e
       if x.reversibility in ("forward_only","manual_rollback_required") and not x.rollback_notes]
print("ok" if not bad else "missing:" + ",".join(bad))
PY
)
echo "complete=$complete unknown=$unknown notes=$notes_ok"
if [ "$complete" = "True" ] && [ "$unknown" = "0" ] && [ "$notes_ok" = "ok" ]; then
  echo "MIGRATION_ROLLBACK_CATALOG_VERIFY: PASS"
  exit 0
fi
echo "MIGRATION_ROLLBACK_CATALOG_VERIFY: FAIL"
exit 1
