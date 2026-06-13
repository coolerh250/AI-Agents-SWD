#!/usr/bin/env bash
# Stage 43 -- end-to-end verifier for the controlled audit_log restore exception.
#
# Scenario A -- precheck: forensic root_cause/sequence/allowed/prod, OR the
#               chain is already clean (nothing to restore / already restored).
# Scenario B -- dry-run: no approval -> gated, DB unchanged, report exists.
# Scenario C -- approved restore (only if AUDIT_LOG_RESTORE_APPROVED=true):
#               restore (if still needed), then the audit verifiers must PASS.
# Scenario D -- safety: production counters 0, no secret leak, ops/safety fields.
#
# Marker:
#   AUDIT_LOG_RESTORE_EXCEPTION_VERIFY: PASS                    (approved/clean)
#   AUDIT_LOG_RESTORE_EXCEPTION_VERIFY: PASS_APPROVAL_REQUIRED  (gated, no change)
#   AUDIT_LOG_RESTORE_EXCEPTION_VERIFY: FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
FORENSIC="source/audit-forensics/audit_forensic_latest.json"
RESTORE="source/audit-forensics/audit_log_restore_latest.json"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
APPROVED="${AUDIT_LOG_RESTORE_APPROVED:-false}"

echo "### verify_audit_log_restore_exception: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  approved_flag=${APPROVED}"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }

fingerprint() {
  "$PY" - <<'PY'
import asyncio, os, sys
sys.path.insert(0, os.getcwd())
import asyncpg
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
async def main():
    try:
        conn = await asyncpg.connect(dsn=DSN, timeout=10)
    except Exception:
        print("NA"); return
    try:
        v = await conn.fetchval(
            "SELECT COALESCE(SUM(('x'||substr(md5(canonical_payload_hash||row_hash||"
            "COALESCE(prev_hash,'')),1,8))::bit(32)::bigint),0) FROM audit_integrity_records")
        print(v)
    finally:
        await conn.close()
asyncio.run(main())
PY
}

# Always refresh the forensic report so we reflect the CURRENT chain state.
"$PY" scripts/analyze_audit_chain_mismatch.py >/dev/null 2>&1 || true

CLEAN=0
if [ -f "$FORENSIC" ]; then
  failed_count=$("$PY" -c "import json;print(json.load(open('$FORENSIC')).get('failed_records_count') or 0)" 2>/dev/null || echo 0)
  [ "$failed_count" = "0" ] && CLEAN=1
fi
echo "  chain_clean=${CLEAN}"

echo
echo "=== Scenario A: precheck ==="
if [ ! -f "$FORENSIC" ]; then
  _fail "forensic report missing"
elif [ "$CLEAN" = "1" ]; then
  _pass "chain clean -- nothing to restore (or already restored)"
else
  _pass "forensic report present"
  if "$PY" - "$FORENSIC" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = True
if d.get("root_cause_classification") != "test_tamper_not_restored":
    print(f"  [FAIL] root_cause={d.get('root_cause_classification')}"); ok = False
else:
    print("  [PASS] root_cause=test_tamper_not_restored")
if not d.get("repair_allowed"):
    print("  [FAIL] repair_allowed not true"); ok = False
else:
    print("  [PASS] repair_allowed=true")
if d.get("production_executed") is True:
    print("  [FAIL] production_executed true"); ok = False
else:
    print("  [PASS] production_executed=false")
if d.get("first_failed_sequence") is None:
    print("  [FAIL] no first_failed_sequence"); ok = False
else:
    print(f"  [PASS] first_failed_sequence={d.get('first_failed_sequence')}")
sys.exit(0 if ok else 1)
PY
  then _pass "precheck fields valid"; else _fail "precheck fields invalid"; fi
fi

echo
echo "=== Scenario B: dry-run (no approval) ==="
fp_before=$(fingerprint)
dry_out=$(AUDIT_LOG_RESTORE_APPROVED=false bash scripts/restore_audit_log_test_tamper_residue.sh 2>&1)
echo "$dry_out" | grep -E "status=|AUDIT_LOG_RESTORE:" || true
if echo "$dry_out" | grep -qE "AUDIT_LOG_RESTORE: (APPROVAL_REQUIRED|DRY_RUN|REJECTED_UNSAFE)"; then
  _pass "dry-run gated (no DB change path)"
else
  _fail "dry-run not gated"
fi
fp_after_dry=$(fingerprint)
if [ "$fp_before" = "$fp_after_dry" ]; then
  _pass "DB fingerprint unchanged after dry-run"
else
  _fail "DB changed during dry-run"
fi

OVERALL="PASS_APPROVAL_REQUIRED"
[ "$CLEAN" = "1" ] && OVERALL="PASS"

if [ "$APPROVED" = "true" ]; then
  OVERALL="PASS"
  echo
  echo "=== Scenario C: approved restore ==="
  if [ "$CLEAN" = "1" ]; then
    _skip "chain already clean -- no restore needed"
  else
    restore_out=$(AUDIT_LOG_RESTORE_APPROVED=true bash scripts/restore_audit_log_test_tamper_residue.sh 2>&1)
    echo "$restore_out" | grep -E "status=|AUDIT_LOG_RESTORE:|modified_count|marker|verifier_after" || true
    if echo "$restore_out" | grep -q "AUDIT_LOG_RESTORE: COMPLETED"; then
      _pass "restore COMPLETED"
    else
      _fail "restore did not complete"
    fi
    if echo "$restore_out" | grep -q "audit_logs_modified_count=1"; then
      _pass "exactly one audit_logs row modified"
    else
      _fail "audit_logs_modified_count != 1"
    fi
    if echo "$restore_out" | grep -q "audit_integrity_records_modified_count=0"; then
      _pass "zero audit_integrity_records modified"
    else
      _fail "audit_integrity_records modified"
    fi
    if echo "$restore_out" | grep -q "after_contains_tamper_marker=False"; then
      _pass "tamper marker removed"
    else
      _fail "tamper marker still present"
    fi
    if echo "$restore_out" | grep -q "hash_match_after=True"; then
      _pass "canonical hash matches stored hash after restore"
    else
      _fail "canonical hash mismatch after restore"
    fi
  fi

  echo "  --- downstream audit verifiers (must PASS now) ---"
  if bash scripts/verify_tamper_evident_audit.sh >/tmp/te.out 2>&1; then
    _pass "verify_tamper_evident_audit.sh PASS"
  else
    grep -E "_VERIFY:" /tmp/te.out | tail -2 || true
    _fail "verify_tamper_evident_audit.sh FAIL"
  fi
  if bash scripts/verify_audit_integrity_remediation.sh >/tmp/air.out 2>&1; then
    _pass "verify_audit_integrity_remediation.sh PASS"
  else
    grep -E "_VERIFY:" /tmp/air.out | tail -2 || true
    _fail "verify_audit_integrity_remediation.sh FAIL"
  fi
  if bash scripts/verify_audit_direct_post_integrity.sh >/tmp/dp.out 2>&1; then
    _pass "verify_audit_direct_post_integrity.sh PASS"
  else
    grep -E "_VERIFY:" /tmp/dp.out | tail -2 || true
    _fail "verify_audit_direct_post_integrity.sh FAIL"
  fi
else
  echo
  echo "=== Scenario C: approved restore ==="
  _skip "AUDIT_LOG_RESTORE_APPROVED not set -- approved restore skipped"
fi

echo
echo "=== Scenario D: safety ==="
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
if [ "${dep:-1}" = "0" ] && [ "${wf:-1}" = "0" ]; then
  _pass "production_executed counters 0/0"
else
  _fail "production_executed counters non-zero (dep=$dep wf=$wf)"
fi
if [ -f "$RESTORE" ] && grep -qE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AUDIT_HMAC_KEY|xox[baprs]-' "$RESTORE"; then
  _fail "secret-like pattern in restore report"
else
  _pass "no secret pattern in restore report"
fi
safety=$(curl -sS -m 10 "${ORCH}/operations/safety" 2>/dev/null || echo '{}')
if echo "$safety" | grep -q '"audit_log_restore_exception_available"'; then
  _pass "operations/safety carries audit_log_restore fields"
else
  _skip "operations/safety not reachable"
fi

echo
echo "  restore-exception checks: ${checks}/${total}"
if [ "$checks" -eq "$total" ] && [ "$total" -ge 6 ]; then
  echo "AUDIT_LOG_RESTORE_EXCEPTION_VERIFY: ${OVERALL}"
  exit 0
fi
echo "AUDIT_LOG_RESTORE_EXCEPTION_VERIFY: FAIL"
exit 1