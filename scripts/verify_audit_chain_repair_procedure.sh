#!/usr/bin/env bash
# Stage 42 -- end-to-end verifier for the controlled repair procedure.
#
# Default behaviour (no AUDIT_CHAIN_REPAIR_APPROVED): the repair must run as
# dry-run / approval-required / skipped-unsafe and make NO database change.
# The verify PASSES as long as the procedure is correctly gated and the
# forensic report is complete -- a still-failing chain is a documented
# blocker, not a verify failure.
#
# If the operator sets AUDIT_CHAIN_REPAIR_APPROVED=true AND the forensic
# report says repair_allowed=true, an approved repair is run and the chain
# must verify afterwards.
#
# Marker: AUDIT_CHAIN_REPAIR_PROCEDURE_VERIFY: PASS/FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
FORENSIC="source/audit-forensics/audit_forensic_latest.json"
REPAIR="source/audit-forensics/audit_repair_latest.json"
APPROVED="${AUDIT_CHAIN_REPAIR_APPROVED:-false}"

echo "### verify_audit_chain_repair_procedure: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  approved_flag=${APPROVED}"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }

# Ensure a forensic report exists first (repair reads it).
echo
echo "=== 0. Forensic report present ==="
if [ ! -f "$FORENSIC" ]; then
    echo "  running analyzer to produce a forensic report..."
    "$PY" scripts/analyze_audit_chain_mismatch.py >/dev/null 2>&1 || true
fi
if [ -f "$FORENSIC" ]; then
    _pass "forensic report present"
else
    _fail "forensic report missing"
    echo "AUDIT_CHAIN_REPAIR_PROCEDURE_VERIFY: FAIL"
    exit 1
fi

repair_allowed=$("$PY" -c "import json,sys;print(json.load(open('$FORENSIC')).get('repair_allowed'))" 2>/dev/null || echo "None")
echo "  forensic repair_allowed=${repair_allowed}"

# Count integrity records before any repair attempt (read-only).
count_before=$("$PY" - <<'PY'
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
        row = await conn.fetchval("SELECT COALESCE(SUM(('x'||substr(md5(canonical_payload_hash||row_hash||COALESCE(prev_hash,'')),1,8))::bit(32)::bigint),0) FROM audit_integrity_records")
        print(row)
    finally:
        await conn.close()
asyncio.run(main())
PY
)
echo "  integrity fingerprint before=${count_before}"

echo
echo "=== 1. Run repair (gated) ==="
repair_out=$(AUDIT_CHAIN_REPAIR_APPROVED="$APPROVED" bash scripts/repair_audit_chain_integrity.sh 2>&1)
echo "$repair_out" | grep -E "status=|AUDIT_CHAIN_REPAIR:|audit_logs_modified|changed_records_count" || true
status_line=$(echo "$repair_out" | grep -E "^AUDIT_CHAIN_REPAIR:" | tail -1)

# audit_logs must NEVER be modified.
if echo "$repair_out" | grep -q "audit_logs_modified=True"; then
    _fail "audit_logs_modified=True -- repair must never modify audit_logs"
else
    _pass "audit_logs not modified"
fi

count_after=$("$PY" - <<'PY'
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
        row = await conn.fetchval("SELECT COALESCE(SUM(('x'||substr(md5(canonical_payload_hash||row_hash||COALESCE(prev_hash,'')),1,8))::bit(32)::bigint),0) FROM audit_integrity_records")
        print(row)
    finally:
        await conn.close()
asyncio.run(main())
PY
)
echo "  integrity fingerprint after=${count_after}"

if [ "$APPROVED" != "true" ] || [ "$repair_allowed" != "True" ]; then
    # No approval (or not allowed): the chain must be UNCHANGED.
    echo
    echo "=== 2. Unapproved / disallowed -> no DB change ==="
    if echo "$status_line" | grep -qE "AUDIT_CHAIN_REPAIR: (APPROVAL_REQUIRED|SKIPPED_UNSAFE|DRY_RUN)"; then
        _pass "repair correctly gated: ${status_line}"
    else
        _fail "expected gated status, got: ${status_line}"
    fi
    if [ "$count_before" = "$count_after" ]; then
        _pass "integrity records unchanged without approval"
    else
        _fail "integrity records changed without approval"
    fi
else
    # Approved AND allowed: an apply must have completed and verified.
    echo
    echo "=== 2. Approved + allowed -> repair applied and verified ==="
    if echo "$status_line" | grep -q "AUDIT_CHAIN_REPAIR: COMPLETED"; then
        _pass "approved repair completed"
    else
        _fail "approved repair did not complete: ${status_line}"
    fi
    if [ -f "$REPAIR" ] && "$PY" -c "import json;d=json.load(open('$REPAIR'));exit(0 if (d.get('verification_after_repair') or {}).get('passed') else 1)" 2>/dev/null; then
        _pass "post-repair verification passed"
    else
        _fail "post-repair verification did not pass"
    fi
fi

echo
echo "=== 3. No secret leak in repair report ==="
if [ -f "$REPAIR" ] && grep -qE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AUDIT_HMAC_KEY|xox[baprs]-' "$REPAIR"; then
    _fail "secret-like pattern in repair report"
else
    _pass "no secret pattern in repair report"
fi

echo
echo "  repair-procedure checks: ${checks}/${total}"
if [ "$checks" -eq "$total" ] && [ "$total" -ge 4 ]; then
    echo "AUDIT_CHAIN_REPAIR_PROCEDURE_VERIFY: PASS"
    exit 0
fi
echo "AUDIT_CHAIN_REPAIR_PROCEDURE_VERIFY: FAIL"
exit 1