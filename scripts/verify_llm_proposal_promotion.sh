#!/usr/bin/env bash
# Stage 31 -- LLM proposal promotion verifier.
#
# Three checks on the local/test stack:
#   1) POST /llm/proposals/<unknown>/promote returns 404 for an
#      unknown proposal id.
#   2) /operations/approval-policies endpoint exists and responds.
#   3) /operations/llm/proposals/<task_id> endpoint exists and
#      responds (the promotion flow is observed via the workflow
#      view's `approval_policy.promotions` array).
#
# production_executed=false must hold throughout.
set -uo pipefail

ORCH="${ORCH_URL:-http://localhost:8000}"

echo "### verify_llm_proposal_promotion: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=4
fail() { echo "  $1: FAIL"; }
pass() { echo "  $1: PASS"; checks=$((checks+1)); }

# 1. Promote unknown proposal -> 404
http=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" \
  -X POST "${ORCH}/llm/proposals/00000000-0000-0000-0000-000000000000/promote" \
  -H "Content-Type: application/json" \
  -d '{"task_id":"stage31-unknown","promoted_by":"verifier"}' || echo "000")
[ "$http" = "404" ] && pass "UNKNOWN_PROPOSAL_404" || fail "UNKNOWN_PROPOSAL_404 (got: $http)"

# 2. /operations/approval-policies reachable
ap_status=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" "${ORCH}/operations/approval-policies?limit=1" || echo "000")
[ "$ap_status" = "200" ] && pass "OPERATIONS_APPROVAL_POLICIES_REACHABLE" || fail "OPERATIONS_APPROVAL_POLICIES_REACHABLE (got: $ap_status)"

# 3. /operations/llm/proposals/<task> reachable
llm_status=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" "${ORCH}/operations/llm/proposals/stage31-smoke" || echo "000")
[ "$llm_status" = "200" ] && pass "OPERATIONS_LLM_PROPOSALS_REACHABLE" || fail "OPERATIONS_LLM_PROPOSALS_REACHABLE (got: $llm_status)"

# 4. Production safety unchanged
safety=$(curl -sS -m 10 "${ORCH}/operations/safety" || echo '{}')
prod=$(echo "$safety" | python3 -c "import json, sys; print(json.load(sys.stdin).get('production_executed_true_count', 999))" 2>/dev/null || echo 999)
[ "$prod" = "0" ] && pass "PRODUCTION_SAFETY_UNCHANGED" || fail "PRODUCTION_SAFETY_UNCHANGED (count=$prod)"

echo
echo "passed ${checks}/${total}"
if [ "$checks" -ge "$total" ]; then
  echo "LLM_PROPOSAL_PROMOTION_VERIFY: PASS"
  exit 0
else
  echo "LLM_PROPOSAL_PROMOTION_VERIFY: FAIL"
  exit 1
fi
