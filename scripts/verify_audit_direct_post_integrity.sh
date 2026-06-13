#!/usr/bin/env bash
# Stage 39 -- audit-service direct POST integrity closure verify.
#
# 1. POST a synthetic audit event to /audit/events.
# 2. Read the operations receipt for the new audit_log_id and confirm the
#    integrity record was created in the same request.
# 3. Confirm missing_integrity_records remains 0 in the operations summary.
# 4. Confirm /operations/audit/verify-chain still returns passed / partial.
#
# Marker: AUDIT_DIRECT_POST_INTEGRITY_VERIFY: PASS / FAIL.

set -uo pipefail

cd "$(dirname "$0")/.."

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
AUDIT="${AUDIT_SERVICE_URL:-http://localhost:8003}"

ts="$(date '+%Y%m%d%H%M%S')"
task_id="stage39-direct-post-${ts}"
echo "### verify_audit_direct_post_integrity: $task_id"

post_body=$(curl -sS -m 10 -X POST "$AUDIT/audit/events" \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$task_id\",\"agent\":\"verify-stage39\",\"decision_type\":\"audit_direct_post_integrity_created\",\"summary\":\"stage39 direct post smoke\",\"result\":\"ok\",\"artifact_refs\":{\"verification_mode\":\"permissive\",\"production_executed\":false}}" 2>/dev/null || echo '{}')

if ! echo "$post_body" | grep -q '"audit_id"'; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (post_failed body=$(echo "$post_body" | head -c 400))"
  exit 1
fi

if ! echo "$post_body" | grep -q '"audit_integrity_created":[[:space:]]*true'; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (integrity_not_created_in_same_txn body=$(echo "$post_body" | head -c 400))"
  exit 1
fi

audit_id=$(echo "$post_body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("audit_id",""))' 2>/dev/null || echo '')
if [ -z "$audit_id" ]; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (missing_audit_id)"
  exit 1
fi
echo "  audit_id=$audit_id"

receipt=$(curl -sS -m 5 "$ORCH/operations/audit/receipt/$audit_id" || echo '{}')
if ! echo "$receipt" | grep -q '"row_hash"'; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (no_integrity_receipt_for_$audit_id)"
  exit 1
fi
if ! echo "$receipt" | grep -q '"signature_verification_status"'; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (receipt_missing_signature_verification_status)"
  exit 1
fi
echo "  receipt: PASS"

integ=$(curl -sS -m 5 "$ORCH/operations/audit/integrity" || echo '{}')
mi=$(echo "$integ" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("missing_integrity_records",-1))' 2>/dev/null || echo -1)
if [ "$mi" != "0" ]; then
  echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (missing_integrity_records=$mi)"
  exit 1
fi
echo "  missing_integrity_records=0"

mode_ok=$(curl -sS -m 15 -X POST "$ORCH/operations/audit/verify-chain?mode=permissive" || echo '{}')
status=$(echo "$mode_ok" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo '')
case "$status" in
  passed|partial)
    echo "  verify-chain=$status"
    ;;
  *)
    echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (verify_chain_status=$status)"
    exit 1
    ;;
esac

# Defensive: ensure the post / receipt / integ payloads do not leak a key.
for body in "$post_body" "$receipt" "$integ"; do
  if grep -qiE '"(key_value|key_bytes|secret_value|AUDIT_HMAC_KEY)"' <<< "$body"; then
    echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: FAIL (key_value_leak)"
    exit 1
  fi
done

echo "AUDIT_DIRECT_POST_INTEGRITY_VERIFY: PASS"
