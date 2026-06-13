#!/usr/bin/env bash
# Stage 42 -- end-to-end verifier for the audit chain forensic analyzer.
#
# Steps:
#   1. run analyze_audit_chain_mismatch.py (read-only)
#   2. verify the forensic report exists
#   3. if the chain is currently failing, verify first_failed_sequence is set
#   4. verify a root cause classification is present
#   5. verify repair_allowed is explicitly true/false
#   6. verify no secret leak in the report
#
# READ-ONLY. Never mutates the DB. Marker: AUDIT_CHAIN_FORENSICS_VERIFY: PASS/FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
REPORT="source/audit-forensics/audit_forensic_latest.json"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"

echo "### verify_audit_chain_forensics: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }

echo
echo "=== 1. Run forensic analyzer (read-only) ==="
if "$PY" scripts/analyze_audit_chain_mismatch.py; then
    _pass "analyze_audit_chain_mismatch.py ran"
else
    _fail "analyze_audit_chain_mismatch.py failed"
fi

echo
echo "=== 2-5. Inspect forensic report ==="
if [ ! -f "$REPORT" ]; then
    _fail "forensic report missing at $REPORT"
    echo "AUDIT_CHAIN_FORENSICS_VERIFY: FAIL"
    exit 1
fi
_pass "forensic report present"

"$PY" - "$REPORT" <<'PY'
import json
import sys

report = json.loads(open(sys.argv[1], encoding="utf-8").read())
failed = report.get("failed_records_count") or 0
first = report.get("first_failed_sequence")
root = report.get("root_cause_classification")
repair_allowed = report.get("repair_allowed")

ok = True
if failed > 0 and first is None:
    print("  [FAIL] chain failing but first_failed_sequence not recorded")
    ok = False
else:
    print(f"  [PASS] first_failed_sequence={first} (failed_records={failed})")

# A verdict must exist: a root cause string when failing, or a clean chain.
if failed > 0 and not root:
    print("  [FAIL] failing chain has no root_cause_classification")
    ok = False
else:
    print(f"  [PASS] root_cause_classification={root}")

if repair_allowed not in (True, False):
    print("  [FAIL] repair_allowed not explicitly true/false")
    ok = False
else:
    print(f"  [PASS] repair_allowed={repair_allowed}")

if report.get("production_executed") is True:
    print("  [FAIL] production_executed must be false for repair eligibility")
    ok = False
else:
    print("  [PASS] production_executed=false")

sys.exit(0 if ok else 1)
PY
if [ $? -eq 0 ]; then
    _pass "forensic report fields valid"
else
    _fail "forensic report fields invalid"
fi

echo
echo "=== 6. No secret leak in report ==="
if grep -qE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AUDIT_HMAC_KEY|"hmac_key"|xox[baprs]-' "$REPORT"; then
    _fail "secret-like pattern found in forensic report"
else
    _pass "no secret pattern in forensic report"
fi

echo
echo "=== 7. operations/audit/forensics/latest reachable ==="
body=$(curl -sS -m 10 "${ORCH}/operations/audit/forensics/latest" 2>/dev/null || echo '{}')
if echo "$body" | grep -q '"available"'; then
    _pass "operations/audit/forensics/latest responded"
else
    echo "  [SKIP] operations endpoint not reachable (orchestrator may be down)"
fi

echo
echo "  forensics checks: ${checks}/${total}"
if [ "$checks" -ge 5 ] && [ "$checks" -eq "$total" ]; then
    echo "AUDIT_CHAIN_FORENSICS_VERIFY: PASS"
    exit 0
fi
echo "AUDIT_CHAIN_FORENSICS_VERIFY: FAIL"
exit 1