#!/usr/bin/env bash
# Stage 34 -- end-to-end verifier for the tamper-evident audit chain.
#
# Drives the backfill + verifier + operations + receipt + tamper-detection
# smokes, then checks production safety counters. Fail-closed: any
# component returning a FAIL aborts.

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_tamper_evident_audit: $(date '+%Y-%m-%d %H:%M:%S %Z')"

step() { echo; echo "=== $1 ==="; }

step "1. Backfill audit integrity for existing audit_logs"
if ! ./scripts/backfill_audit_integrity.sh; then
  echo "TAMPER_EVIDENT_AUDIT_VERIFY: FAIL (backfill)"
  exit 1
fi

step "2. Verify the audit chain"
if ! ./scripts/verify_audit_integrity.sh; then
  echo "TAMPER_EVIDENT_AUDIT_VERIFY: FAIL (verify_chain)"
  exit 1
fi

step "3. GET /operations/audit/integrity"
integ=$(curl -sS -m 5 "$ORCH/operations/audit/integrity" || echo '{}')
echo "$integ" | python3 -m json.tool 2>/dev/null | head -30 || echo "$integ" | head -c 600
echo
if echo "$integ" | grep -q '"audit_integrity_enabled"'; then
  echo "AUDIT_INTEGRITY_ENDPOINT: PASS"
else
  echo "AUDIT_INTEGRITY_ENDPOINT: FAIL"
  exit 1
fi

step "4. POST /operations/audit/verify-chain"
# Client timeout is generous (60s): the chain has grown to ~300k rows and a full
# verification legitimately takes ~10s+ and grows with the chain. This is only
# the HTTP client wait -- the endpoint still performs the identical strict
# verification and the status gate below is unchanged (passed|partial only).
verify=$(curl -sS -m 60 -X POST "$ORCH/operations/audit/verify-chain" || echo '{}')
echo "$verify" | python3 -m json.tool 2>/dev/null | head -25 || echo "$verify" | head -c 600
echo
case "$(echo "$verify" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)" in
  passed|partial)
    echo "AUDIT_VERIFY_CHAIN_ENDPOINT: PASS"
    ;;
  *)
    echo "AUDIT_VERIFY_CHAIN_ENDPOINT: FAIL"
    exit 1
    ;;
esac

step "5. GET /operations/audit/verify-chain/latest"
latest=$(curl -sS -m 5 "$ORCH/operations/audit/verify-chain/latest" || echo '{}')
echo "$latest" | python3 -m json.tool 2>/dev/null | head -15 || echo "$latest" | head -c 400
echo
if echo "$latest" | grep -qE '"status":\s*"(passed|partial|failed|error|not_run)"'; then
  echo "AUDIT_VERIFY_CHAIN_LATEST_ENDPOINT: PASS"
else
  echo "AUDIT_VERIFY_CHAIN_LATEST_ENDPOINT: FAIL"
  exit 1
fi

step "6. GET /operations/audit/receipt/{audit_log_id} (latest audit_logs row)"
latest_audit_id=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT id FROM audit_logs ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | tr -d '[:space:]')
if [ -z "$latest_audit_id" ]; then
  echo "no audit_logs rows -- skipping receipt smoke"
  echo "AUDIT_RECEIPT_ENDPOINT: SKIPPED"
else
  receipt=$(curl -sS -m 5 "$ORCH/operations/audit/receipt/$latest_audit_id" || echo '{}')
  echo "$receipt" | python3 -m json.tool 2>/dev/null | head -25 || echo "$receipt" | head -c 600
  echo
  if echo "$receipt" | grep -q '"row_hash"'; then
    echo "AUDIT_RECEIPT_ENDPOINT: PASS"
  else
    echo "AUDIT_RECEIPT_ENDPOINT: FAIL"
    exit 1
  fi
fi

step "7. Tamper detection smoke (savepoint + rollback)"
if ! ./scripts/simulate_audit_tamper_detection.sh; then
  echo "TAMPER_EVIDENT_AUDIT_VERIFY: FAIL (tamper_detection)"
  exit 1
fi

step "8. No secret leak (key value / preview length sanity)"
# The receipt only ever exposes the signing_key_id + an 8-char preview.
# Quick belt-and-braces grep on the operations payloads:
for body in "$integ" "$verify" "$latest" "${receipt:-{}}"; do
  if echo "$body" | grep -qE 'AUDIT_HMAC_KEY=|"hmac_signature":\s*"[A-Fa-f0-9]{32,}"'; then
    echo "AUDIT_INTEGRITY_NO_SECRET_LEAK: FAIL"
    exit 1
  fi
done
echo "AUDIT_INTEGRITY_NO_SECRET_LEAK: PASS"

step "9. production safety counters"
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true=$dep"
echo "  workflow_states.production_executed_true=$wf"
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "AUDIT_INTEGRITY_PRODUCTION_SAFETY: PASS"
else
  echo "AUDIT_INTEGRITY_PRODUCTION_SAFETY: FAIL"
  exit 1
fi

echo
echo "TAMPER_EVIDENT_AUDIT_VERIFY: PASS"
echo "VERIFY_TAMPER_EVIDENT_AUDIT_DONE"
