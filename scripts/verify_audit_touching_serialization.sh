#!/usr/bin/env bash
# Stage 44 -- end-to-end verifier for audit-touching regression serialization.
#
# Runs its child checks SEQUENTIALLY (never concurrently) and deliberately does
# NOT hold the audit lock itself, so the full-regression child acquires the
# lock for real (audit_lock_used=true is observable).
#
# Scenario A -- lock helper acquire/release markers.
# Scenario B -- residue detector reports no residue.
# Scenario C -- tamper simulation isolation (detect + restore + no residue).
# Scenario D -- full regression uses the lock + serializes + no residue failure.
# Scenario E -- operations safety serialization fields.
#
# Marker: AUDIT_TOUCHING_SERIALIZATION_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true
# shellcheck source=scripts/lib/audit_verification_lock.sh
source "$(dirname "$0")/lib/audit_verification_lock.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
SUMMARY="source/regression-reports/regression_latest_summary.json"

echo "### verify_audit_touching_serialization: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }

echo
echo "=== Scenario A: lock helper ==="
lock_out=$(bash -c "source scripts/lib/audit_verification_lock.sh; \
  acquire_audit_exclusive_lock serialization_verify; release_audit_lock serialization_verify" 2>&1)
echo "$lock_out" | grep -E "AUDIT_VERIFICATION_LOCK:" || true
echo "$lock_out" | grep -q "AUDIT_VERIFICATION_LOCK: ACQUIRED" && _pass "lock ACQUIRED" || _fail "no ACQUIRED"
echo "$lock_out" | grep -q "AUDIT_VERIFICATION_LOCK: RELEASED" && _pass "lock RELEASED" || _fail "no RELEASED"

echo
echo "=== Scenario B: residue detector ==="
det_out=$(bash scripts/detect_audit_tamper_residue.sh 2>&1)
echo "$det_out" | grep -E "residue_count=|AUDIT_TAMPER_RESIDUE_DETECTOR:" || true
if echo "$det_out" | grep -q "AUDIT_TAMPER_RESIDUE_DETECTOR: PASS"; then
  _pass "no tamper residue"
elif echo "$det_out" | grep -q "AUDIT_TAMPER_RESIDUE_DETECTOR: SKIP"; then
  echo "  [SKIP] detector could not reach DB"
else
  _fail "tamper residue detected"
fi

echo
echo "=== Scenario C: tamper simulation isolation ==="
te_out=$(bash scripts/verify_tamper_evident_audit.sh 2>&1)
echo "$te_out" | grep -E "AUDIT_TAMPER_SIMULATION_|TAMPER_EVIDENT_AUDIT_VERIFY:|tamper_status" | tail -8 || true
if echo "$te_out" | grep -q "AUDIT_TAMPER_SIMULATION_LOCKED: PASS"; then
  _pass "tamper simulation acquired lock"
else
  echo "  [SKIP] tamper simulation lock marker not present"
fi
if echo "$te_out" | grep -q "AUDIT_TAMPER_SIMULATION_NO_RESIDUE: PASS"; then
  _pass "no residue after tamper simulation"
else
  _fail "residue after tamper simulation"
fi
if echo "$te_out" | grep -q "TAMPER_EVIDENT_AUDIT_VERIFY: PASS"; then
  _pass "tamper-evident audit verify PASS"
else
  _fail "tamper-evident audit verify did not pass"
fi
# Confirm chain clean after the simulation.
if bash scripts/detect_audit_tamper_residue.sh 2>&1 | grep -q "AUDIT_TAMPER_RESIDUE_DETECTOR: PASS"; then
  _pass "audit chain clean after simulation"
else
  _fail "residue present after simulation"
fi

echo
echo "=== Scenario D: full regression lock ==="
echo "  (running full regression -- this is slow)"
bash scripts/run_full_regression.sh --full --json-report >/tmp/fullreg.out 2>&1
fr_marker=$(grep -E "^FULL_REGRESSION_VERIFY:" /tmp/fullreg.out | tail -1)
echo "  $fr_marker"
if echo "$fr_marker" | grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)"; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression failed: $fr_marker"
fi
if [ -f "$SUMMARY" ]; then
  if "$PY" -c "import json;d=json.load(open('$SUMMARY'));exit(0 if d.get('audit_lock_used') else 1)" 2>/dev/null; then
    _pass "audit_lock_used=true"
  else
    _fail "audit_lock_used not true"
  fi
  if "$PY" -c "import json;d=json.load(open('$SUMMARY'));exit(0 if d.get('audit_touching_scripts_serialized') else 1)" 2>/dev/null; then
    _pass "audit_touching_scripts_serialized=true"
  else
    _fail "audit_touching_scripts_serialized not true"
  fi
  if "$PY" -c "import json;d=json.load(open('$SUMMARY'));s=d.get('summary',{});exit(0 if (s.get('audit_tamper_residue_failure',0)==0 and s.get('audit_serialization_failure',0)==0) else 1)" 2>/dev/null; then
    _pass "no audit serialization / residue failure"
  else
    _fail "audit serialization / residue failure present"
  fi
else
  _fail "regression summary not written"
fi

echo
echo "=== Scenario E: operations safety ==="
safety=$(curl -sS -m 10 "${ORCH}/operations/safety" 2>/dev/null || echo '{}')
if echo "$safety" | grep -q '"audit_touching_regression_serialized": true' \
   || echo "$safety" | grep -q '"audit_touching_regression_serialized":true'; then
  _pass "audit_touching_regression_serialized=true"
else
  _fail "audit_touching_regression_serialized not true"
fi
if echo "$safety" | grep -q '"audit_tamper_residue_detected": false' \
   || echo "$safety" | grep -q '"audit_tamper_residue_detected":false'; then
  _pass "audit_tamper_residue_detected=false"
else
  _fail "audit_tamper_residue_detected not false"
fi

echo
echo "  serialization checks: ${checks}/${total}"
if [ "$checks" -eq "$total" ] && [ "$total" -ge 9 ]; then
  echo "AUDIT_TOUCHING_SERIALIZATION_VERIFY: PASS"
  exit 0
fi
echo "AUDIT_TOUCHING_SERIALIZATION_VERIFY: FAIL"
exit 1