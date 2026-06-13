#!/usr/bin/env bash
# verify_incident_response.sh
# Stage 40 -- Incident Response lifecycle verification.
#
# Steps:
#   1. Create incident via alert
#   2. Acknowledge incident
#   3. Resolve incident
#   4. Close incident
#   5. Create SEV1 incident
#   6. Verify postmortem required
#   7. Create postmortem draft
#   8. Verify lifecycle timeline
#   9. Verify safety fields
#   10. Verify no production_executed
#
# Output: INCIDENT_RESPONSE_VERIFY: PASS

set -euo pipefail

BASE_URL="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0

_fail() { echo "FAIL: $*"; FAIL=1; }
_pass() { echo "PASS: $*"; }

echo "--- verify_incident_response"

# ---------------------------------------------------------------------------
# Step 1: Create incident via alert receiver
# ---------------------------------------------------------------------------
alert_resp=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/generic" \
  -H 'Content-Type: application/json' \
  -d "{\"source\":\"synthetic_test\",\"alert_name\":\"IR_Verify_$(date +%s)\",\"severity\":\"warning\",\"labels\":{},\"annotations\":{}}" \
  || echo '{}')

INC_ID=$(echo "$alert_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("incident_id",""))' 2>/dev/null || echo '')
if [ -n "$INC_ID" ] && [ "$INC_ID" != "None" ]; then
  _pass "1: incident created via alert (id=$INC_ID)"
else
  _fail "1: no incident_id returned"
  echo "INCIDENT_RESPONSE_VERIFY: FAIL"
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: Acknowledge
# ---------------------------------------------------------------------------
ack_resp=$(curl -sS -m 10 -X POST "$BASE_URL/operations/incidents/$INC_ID/acknowledge" \
  -H 'Content-Type: application/json' \
  -d '{}' || echo '{}')
ack_status=$(echo "$ack_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo '')
if [ "$ack_status" = "acknowledged" ]; then
  _pass "2: incident acknowledged"
else
  _fail "2: acknowledge failed (status=$ack_status)"
fi

# ---------------------------------------------------------------------------
# Step 3: Resolve
# ---------------------------------------------------------------------------
resolve_resp=$(curl -sS -m 10 -X POST "$BASE_URL/operations/incidents/$INC_ID/resolve" \
  -H 'Content-Type: application/json' \
  -d '{}' || echo '{}')
res_status=$(echo "$resolve_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo '')
if [ "$res_status" = "resolved" ]; then
  _pass "3: incident resolved"
else
  _fail "3: resolve failed (status=$res_status)"
fi

# ---------------------------------------------------------------------------
# Step 4: Close
# ---------------------------------------------------------------------------
close_resp=$(curl -sS -m 10 -X POST "$BASE_URL/operations/incidents/$INC_ID/close" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"verified resolved"}' || echo '{}')
close_status=$(echo "$close_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo '')
if [ "$close_status" = "closed" ]; then
  _pass "4: incident closed"
else
  _fail "4: close failed (status=$close_status)"
fi

# ---------------------------------------------------------------------------
# Step 5: Create SEV1 incident
# ---------------------------------------------------------------------------
sev1_resp=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/alertmanager" \
  -H 'Content-Type: application/json' \
  -d "{\"receiver\":\"verify\",\"status\":\"firing\",\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"IR_SEV1_Verify_$(date +%s)\",\"severity\":\"critical\",\"instance\":\"verify-sev1\"},\"annotations\":{\"summary\":\"verify sev1\"},\"startsAt\":\"2026-06-01T00:00:00Z\",\"endsAt\":\"0001-01-01T00:00:00Z\",\"fingerprint\":\"verify-sev1-fp-$(date +%s)\"}]}" \
  || echo '{}')

SEV1_INC=$(echo "$sev1_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("incident_id","") if r else "")' 2>/dev/null || echo '')
sev1_action=$(echo "$sev1_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("action","") if r else "")' 2>/dev/null || echo '')
if [ "$sev1_action" = "created" ] && [ -n "$SEV1_INC" ] && [ "$SEV1_INC" != "None" ]; then
  _pass "5: SEV1 incident created (id=$SEV1_INC)"
else
  _fail "5: SEV1 incident not created (action=$sev1_action)"
fi

# ---------------------------------------------------------------------------
# Step 6: Verify postmortem required
# ---------------------------------------------------------------------------
if [ -n "$SEV1_INC" ] && [ "$SEV1_INC" != "None" ]; then
  sev1_detail=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$SEV1_INC" || echo '{}')
  pm_req=$(echo "$sev1_detail" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("postmortem_required",""))' 2>/dev/null || echo '')
  if [ "$pm_req" = "True" ]; then
    _pass "6: postmortem_required=true for SEV1"
  else
    _fail "6: postmortem_required not true for SEV1 (got: $pm_req)"
  fi
fi

# ---------------------------------------------------------------------------
# Step 7: Create postmortem draft
# ---------------------------------------------------------------------------
if [ -n "$SEV1_INC" ] && [ "$SEV1_INC" != "None" ]; then
  pm_resp=$(curl -sS -m 10 -X POST "$BASE_URL/operations/incidents/$SEV1_INC/postmortem" \
    -H 'Content-Type: application/json' \
    -d '{"summary":"SEV1 test postmortem draft","owner":"verify-script"}' \
    || echo '{}')
  pm_status=$(echo "$pm_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); pm=d.get("postmortem",{}); print(pm.get("status",""))' 2>/dev/null || echo '')
  if [ "$pm_status" = "draft" ]; then
    _pass "7: postmortem draft created"
  else
    _fail "7: postmortem draft not created (status=$pm_status)"
  fi
fi

# ---------------------------------------------------------------------------
# Step 8: Verify lifecycle timeline
# ---------------------------------------------------------------------------
timeline=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$INC_ID/timeline" || echo '{}')
event_count=$(echo "$timeline" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("event_count",0))' 2>/dev/null || echo '0')
if [ "$event_count" -gt "0" ]; then
  _pass "8: lifecycle timeline has $event_count events"
else
  _fail "8: no lifecycle events"
fi

# ---------------------------------------------------------------------------
# Step 9: Verify safety fields
# ---------------------------------------------------------------------------
safety=$(curl -sS -m 15 "$BASE_URL/operations/safety" || echo '{}')
ir_enabled=$(echo "$safety" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("incident_response_enabled",""))' 2>/dev/null || echo '')
real_esc=$(echo "$safety" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("real_incident_escalation_enabled",""))' 2>/dev/null || echo '')
auto_rem=$(echo "$safety" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("incident_auto_remediation_enabled",""))' 2>/dev/null || echo '')

if [ "$ir_enabled" = "True" ]; then
  _pass "9: incident_response_enabled=true"
else
  _fail "9: incident_response_enabled not true (got: $ir_enabled)"
fi

if [ "$real_esc" = "False" ]; then
  _pass "9: real_incident_escalation_enabled=false"
else
  _fail "9: real_incident_escalation_enabled not false"
fi

if [ "$auto_rem" = "False" ]; then
  _pass "9: incident_auto_remediation_enabled=false"
else
  _fail "9: incident_auto_remediation_enabled not false"
fi

# ---------------------------------------------------------------------------
# Step 10: Verify no production_executed
# ---------------------------------------------------------------------------
prod_count=$(echo "$safety" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("production_executed_true_count",0))' 2>/dev/null || echo '0')
if [ "$prod_count" = "0" ]; then
  _pass "10: production_executed_true_count=0"
else
  _fail "10: production_executed_true_count=$prod_count (must be 0)"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "verify_incident_response: PASS"
  echo "INCIDENT_RESPONSE_VERIFY: PASS"
else
  echo "verify_incident_response: FAIL"
  echo "INCIDENT_RESPONSE_VERIFY: FAIL"
  exit 1
fi
