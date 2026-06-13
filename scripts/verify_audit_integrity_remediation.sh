#!/usr/bin/env bash
# Stage 39 -- end-to-end verifier for the audit integrity remediation work.
#
# Sequence:
#   1. HMAC key rotation (in-process; no DB write).
#   2. Direct POST integrity closure (live audit-service + orchestrator).
#   3. Concurrency smoke (delegates to check_runtime_state.sh markers).
#   4. Tamper-evident audit verify (Stage 34 regression).
#   5. No-secret-leak grep on every emitted payload.
#
# Marker: AUDIT_INTEGRITY_REMEDIATION_VERIFY: PASS / FAIL.

set -uo pipefail

cd "$(dirname "$0")/.."

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_audit_integrity_remediation: $(date '+%Y-%m-%d %H:%M:%S %Z')"

step() { echo; echo "=== $1 ==="; }

step "1. HMAC key rotation"
if ! ./scripts/verify_audit_hmac_key_rotation.sh; then
  echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (key_rotation)"
  exit 1
fi

step "2. Direct POST integrity closure"
if ! ./scripts/verify_audit_direct_post_integrity.sh; then
  echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (direct_post)"
  exit 1
fi

step "3. Concurrency smokes via runtime check"
runtime_out=$(./scripts/check_runtime_state.sh 2>&1 || true)
echo "$runtime_out" | grep -E "AUDIT_INTEGRITY_CONCURRENCY_SMOKE|AUDIT_DIRECT_POST_NO_GAP_SMOKE|AUDIT_KEYRING_SAFETY_SMOKE" || true
if grep -q "AUDIT_INTEGRITY_CONCURRENCY_SMOKE: PASS" <<< "$runtime_out" \
  && grep -q "AUDIT_DIRECT_POST_NO_GAP_SMOKE: PASS" <<< "$runtime_out"; then
  echo "  concurrency smokes: PASS"
else
  echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (concurrency_smoke)"
  exit 1
fi

step "4. Tamper-evident audit regression"
if ! ./scripts/verify_tamper_evident_audit.sh; then
  echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (tamper_evident)"
  exit 1
fi

step "5. No-secret-leak scan on Stage 39 surfaces"
au_integ=$(curl -sS -m 5 "$ORCH/operations/audit/integrity" || echo '{}')
au_keyring=$(curl -sS -m 5 "$ORCH/operations/audit/keyring" || echo '{}')
safety=$(curl -sS -m 5 "$ORCH/operations/safety" || echo '{}')
for body in "$au_integ" "$au_keyring" "$safety"; do
  if grep -qiE '"(key_value|key_bytes|secret_value)"' <<< "$body"; then
    echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (key_value_leak)"
    exit 1
  fi
done
echo "  no-secret-leak: PASS"

step "6. production safety counters"
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true=$dep"
echo "  workflow_states.production_executed_true=$wf"
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "  production_safety: PASS"
else
  echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: FAIL (production_safety)"
  exit 1
fi

echo
echo "AUDIT_INTEGRITY_REMEDIATION_VERIFY: PASS"
echo "VERIFY_AUDIT_INTEGRITY_REMEDIATION_DONE"
