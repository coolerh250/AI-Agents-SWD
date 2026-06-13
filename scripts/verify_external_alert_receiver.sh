#!/usr/bin/env bash
# verify_external_alert_receiver.sh
# Stage 40 -- External Alert Receiver verification.
#
# Scenarios:
#   A - health check
#   B - Alertmanager payload → incident created
#   C - generic payload → incident created
#   D - deduplification
#   E - redaction
#   F - unauthorized (when auth configured)
#
# Output: EXTERNAL_ALERT_RECEIVER_VERIFY: PASS

set -euo pipefail

BASE_URL="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0

_fail() { echo "FAIL: $*"; FAIL=1; }
_pass() { echo "PASS: $*"; }

echo "--- verify_external_alert_receiver"

# ---------------------------------------------------------------------------
# Scenario A -- health
# ---------------------------------------------------------------------------
health=$(curl -sS -m 10 "$BASE_URL/alerts/health" || echo '{}')
recv_enabled=$(echo "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("receiver_enabled",""))' 2>/dev/null || echo '')
prod_exec=$(echo "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("production_executed",""))' 2>/dev/null || echo '')
real_esc=$(echo "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("real_escalation_enabled",""))' 2>/dev/null || echo '')

if [ "$recv_enabled" = "True" ]; then
  _pass "A: receiver_enabled=true"
else
  _fail "A: receiver_enabled not true (got: $recv_enabled)"
fi

if [ "$prod_exec" = "False" ]; then
  _pass "A: production_executed=false"
else
  _fail "A: production_executed not false (got: $prod_exec)"
fi

if [ "$real_esc" = "False" ]; then
  _pass "A: real_escalation_enabled=false"
else
  _fail "A: real_escalation_enabled not false (got: $real_esc)"
fi

# ---------------------------------------------------------------------------
# Scenario B -- Alertmanager SEV1 payload
# ---------------------------------------------------------------------------
AM_FP="verify-am-fp-$(date +%s)"
am_resp=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/alertmanager" \
  -H 'Content-Type: application/json' \
  -d "{\"receiver\":\"test\",\"status\":\"firing\",\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"VerifyHostDown\",\"severity\":\"critical\",\"instance\":\"verify-host\"},\"annotations\":{\"summary\":\"verify test\"},\"startsAt\":\"2026-06-01T00:00:00Z\",\"endsAt\":\"0001-01-01T00:00:00Z\",\"fingerprint\":\"$AM_FP\"}]}" \
  || echo '{}')

am_action=$(echo "$am_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("action","") if r else "")' 2>/dev/null || echo '')
am_sev=$(echo "$am_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("severity","") if r else "")' 2>/dev/null || echo '')
am_dry=$(echo "$am_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("dry_run",""))' 2>/dev/null || echo '')
am_inc=$(echo "$am_resp" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("incident_id","") if r else "")' 2>/dev/null || echo '')

if [ "$am_action" = "created" ]; then
  _pass "B: Alertmanager alert created incident"
else
  _fail "B: Alertmanager alert did not create incident (action=$am_action)"
fi

if [ "$am_sev" = "SEV1_CRITICAL" ]; then
  _pass "B: severity normalized to SEV1_CRITICAL"
else
  _fail "B: severity not normalized correctly (got: $am_sev)"
fi

if [ "$am_dry" = "True" ]; then
  _pass "B: dry_run=true"
else
  _fail "B: dry_run not true"
fi

# Verify incident in operations
if [ -n "$am_inc" ] && [ "$am_inc" != "None" ]; then
  inc_body=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$am_inc" || echo '{}')
  inc_status=$(echo "$inc_body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo '')
  if [ "$inc_status" = "open" ]; then
    _pass "B: incident_id=$am_inc status=open in operations"
  else
    _fail "B: incident $am_inc status=$inc_status"
  fi

  # Verify lifecycle events
  lc=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$am_inc/timeline" || echo '{}')
  lc_count=$(echo "$lc" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("event_count",0))' 2>/dev/null || echo '0')
  if [ "$lc_count" -gt "0" ]; then
    _pass "B: lifecycle events recorded (count=$lc_count)"
  else
    _fail "B: no lifecycle events"
  fi

  # Verify alerts linked
  alerts_body=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$am_inc/alerts" || echo '{}')
  alert_count=$(echo "$alerts_body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("alert_count",0))' 2>/dev/null || echo '0')
  if [ "$alert_count" -gt "0" ]; then
    _pass "B: alert linked to incident"
  else
    _fail "B: no alerts linked"
  fi
else
  _fail "B: no incident_id returned"
fi

# ---------------------------------------------------------------------------
# Scenario C -- generic SEV3 payload
# ---------------------------------------------------------------------------
gen_resp=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/generic" \
  -H 'Content-Type: application/json' \
  -d "{\"source\":\"synthetic_test\",\"alert_name\":\"VerifyGenericAlert_$(date +%s)\",\"severity\":\"warning\",\"labels\":{\"component\":\"orchestrator\"},\"annotations\":{\"summary\":\"verify generic\"}}" \
  || echo '{}')

gen_action=$(echo "$gen_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("action",""))' 2>/dev/null || echo '')
if [ "$gen_action" = "created" ]; then
  _pass "C: generic alert created incident"
else
  _fail "C: generic alert did not create incident (action=$gen_action)"
fi

# ---------------------------------------------------------------------------
# Scenario D -- deduplification
# ---------------------------------------------------------------------------
DEDUP_FP="verify-dedup-fp-$(date +%s)"
DEDUP_ALERT="VerifyDedup_$(date +%s)"

dedup1=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/alertmanager" \
  -H 'Content-Type: application/json' \
  -d "{\"receiver\":\"test\",\"status\":\"firing\",\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"$DEDUP_ALERT\",\"severity\":\"warning\",\"instance\":\"dedup-host\"},\"annotations\":{},\"startsAt\":\"2026-06-01T00:00:00Z\",\"endsAt\":\"0001-01-01T00:00:00Z\",\"fingerprint\":\"$DEDUP_FP\"}]}" \
  || echo '{}')

dedup2=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/alertmanager" \
  -H 'Content-Type: application/json' \
  -d "{\"receiver\":\"test\",\"status\":\"firing\",\"alerts\":[{\"status\":\"firing\",\"labels\":{\"alertname\":\"$DEDUP_ALERT\",\"severity\":\"warning\",\"instance\":\"dedup-host\"},\"annotations\":{},\"startsAt\":\"2026-06-01T00:00:00Z\",\"endsAt\":\"0001-01-01T00:00:00Z\",\"fingerprint\":\"$DEDUP_FP\"}]}" \
  || echo '{}')

d1_action=$(echo "$dedup1" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("action","") if r else "")' 2>/dev/null || echo '')
d2_action=$(echo "$dedup2" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("action","") if r else "")' 2>/dev/null || echo '')
d1_inc=$(echo "$dedup1" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("incident_id","") if r else "")' 2>/dev/null || echo '')
d2_inc=$(echo "$dedup2" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("results",[]); print(r[0].get("incident_id","") if r else "")' 2>/dev/null || echo '')

if [ "$d1_action" = "created" ] && [ "$d2_action" = "deduplicated" ]; then
  _pass "D: second alert deduplicated"
elif [ "$d1_inc" = "$d2_inc" ] && [ -n "$d1_inc" ]; then
  _pass "D: both alerts linked to same incident"
else
  _fail "D: dedup not working (d1=$d1_action/$d1_inc, d2=$d2_action/$d2_inc)"
fi

# ---------------------------------------------------------------------------
# Scenario E -- redaction
# ---------------------------------------------------------------------------
RED_TS=$(date +%s)
red_resp=$(curl -sS -m 15 -X POST "$BASE_URL/alerts/generic" \
  -H 'Content-Type: application/json' \
  -d "{\"source\":\"synthetic_test\",\"alert_name\":\"VerifyRedaction_${RED_TS}\",\"severity\":\"info\",\"labels\":{\"token\":\"super-secret-token\",\"name\":\"safe-label\"},\"annotations\":{\"password\":\"hunter2\",\"info\":\"ok\"}}" \
  || echo '{}')

red_inc=$(echo "$red_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("incident_id",""))' 2>/dev/null || echo '')
if [ -n "$red_inc" ] && [ "$red_inc" != "None" ]; then
  red_alerts=$(curl -sS -m 10 "$BASE_URL/operations/incidents/$red_inc/alerts" || echo '{}')
  if echo "$red_alerts" | grep -q "REDACTED"; then
    _pass "E: secret fields redacted in stored alert"
  elif echo "$red_alerts" | grep -qiE '"token".*"super-secret|"password".*"hunter2'; then
    _fail "E: secret not redacted in stored alert"
  else
    _pass "E: no secret visible in operations output"
  fi
  if echo "$red_alerts" | grep -q "super-secret-token"; then
    _fail "E: raw token value found in operations response"
  else
    _pass "E: no raw token in operations response"
  fi
else
  _fail "E: redaction alert not created"
fi

# ---------------------------------------------------------------------------
# Scenario F -- unauthorized (only when auth is configured)
# ---------------------------------------------------------------------------
auth_mode=$(echo "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("auth_mode",""))' 2>/dev/null || echo '')
if [ "$auth_mode" = "shared_secret" ]; then
  bad_resp=$(curl -sS -o /dev/null -w "%{http_code}" -m 10 -X POST "$BASE_URL/alerts/generic" \
    -H 'Content-Type: application/json' \
    -H 'X-AIAGENTS-ALERT-SIGNATURE: bad-sig' \
    -d '{"source":"test","alert_name":"auth_test","severity":"info","labels":{}}' \
    || echo '000')
  if [ "$bad_resp" = "403" ] || [ "$bad_resp" = "401" ]; then
    _pass "F: unauthorized payload rejected (HTTP $bad_resp)"
  else
    _fail "F: unauthorized payload not rejected (HTTP $bad_resp)"
  fi
else
  _pass "F: SKIP (local_test_unsigned mode — no auth check)"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "verify_external_alert_receiver: PASS"
  echo "EXTERNAL_ALERT_RECEIVER_VERIFY: PASS"
else
  echo "verify_external_alert_receiver: FAIL"
  echo "EXTERNAL_ALERT_RECEIVER_VERIFY: FAIL"
  exit 1
fi
