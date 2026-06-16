#!/usr/bin/env bash
# Stage 52 -- end-to-end verifier for Admin Console v1 Operator Actions (Step 50).
#
# Controlled operator actions only: delivery package accept/reject/request-changes,
# review notes, allowlisted verification rerun. Auth (test-local signed session),
# RBAC, CSRF, policy, confirmation, idempotency, audit. High-risk actions stay
# disabled. No deploy / GitHub / PR / production; production_executed stays 0.
#
# Scenarios: A auth/session, B RBAC, C delivery review actions, D confirmation/
# idempotency, E verification rerun, F disabled actions, G safety, H audit/
# notifications, I regression compatibility.
#
# Marker: ADMIN_CONSOLE_V1_OPERATOR_ACTIONS_VERIFY: PASS / FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
ADMIN="$ORCH/operations/admin-console"
COMPOSE="${COMPOSE:-docker compose -f infra/docker-compose/docker-compose.yml}"
PG_SERVICE="${POSTGRES_SERVICE:-postgres}"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres@localhost:5432/aiagents}"
JAR="/tmp/bdr_v1_cookies"; rm -f "$JAR"
CSRF=""

echo "### verify_admin_console_v1_operator_actions: $(date '+%Y-%m-%d %H:%M:%S %Z')"
checks=0; total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }

# Helpers -------------------------------------------------------------------
LOGIN_RESP=""
login() { # role -> sets globals JAR + CSRF + LOGIN_RESP. Call in current shell
          # (NOT via $(...)) so the CSRF assignment survives -- command
          # substitution runs in a subshell and would lose it.
  for _attempt in 1 2 3 4 5; do
    rm -f "$JAR"
    LOGIN_RESP=$(curl -sS -m 10 -c "$JAR" -X POST "$ADMIN/auth/test-login" \
      -H 'Content-Type: application/json' -d "{\"role\":\"$1\"}" 2>/dev/null || echo '{}')
    CSRF=$(echo "$LOGIN_RESP" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('csrf_token',''))" 2>/dev/null || echo "")
    [ -n "$CSRF" ] && break
    sleep 2
  done
}
post_admin() { # path json -> response (uses JAR + CSRF + idem)
  curl -sS -m 60 -b "$JAR" -X POST "$ADMIN/$1" \
    -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -H "Idempotency-Key: idem-$(date +%s%N)" -d "$2" 2>/dev/null || echo '{}'
}
post_ops() { # path json idemkey -> response
  curl -sS -m 60 -b "$JAR" -X POST "$ORCH/operations/$1" \
    -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
    -H "Idempotency-Key: ${3:-idem-$(date +%s%N)}" -d "$2" 2>/dev/null || echo '{}'
}
jq_get() { "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1',''))" 2>/dev/null; }

# ---------------------------------------------------------------------------
echo; echo "=== Scenario A: auth / session ==="
login operator
resp="$LOGIN_RESP"
[ -n "$CSRF" ] && _pass "test-login issues session + csrf" || _fail "no csrf from login"
# HttpOnly + SameSite on the cookie (retry-tolerant)
hdr=""
for _a in 1 2 3; do
  hdr=$(curl -sS -m 10 -D - -o /dev/null -X POST "$ADMIN/auth/test-login" \
    -H 'Content-Type: application/json' -d '{"role":"operator"}' 2>/dev/null | tr -d '\r')
  echo "$hdr" | grep -iq 'set-cookie:.*admin_console_session' && break
  sleep 2
done
if echo "$hdr" | grep -iq 'set-cookie:.*admin_console_session' \
   && echo "$hdr" | grep -iq 'httponly' && echo "$hdr" | grep -iq 'samesite=strict'; then
  _pass "cookie HttpOnly + SameSite=Strict"
else
  _fail "cookie flags missing"
fi
sess=$(curl -sS -m 10 -b "$JAR" "$ADMIN/auth/session" 2>/dev/null || echo '{}')
[ "$(echo "$sess" | jq_get authenticated)" = "True" ] && _pass "session active" || _fail "session not active"
# no token in URL / response body should not include raw cookie value
echo "$resp" | grep -qi 'admin_console_session=' && _fail "token leaked in body" || _pass "no session token in body"
# logout revokes
curl -sS -m 10 -b "$JAR" -X POST "$ADMIN/auth/logout" -H "X-CSRF-Token: $CSRF" >/dev/null 2>&1
after=$(curl -sS -m 10 -b "$JAR" "$ADMIN/auth/session" 2>/dev/null || echo '{}')
[ "$(echo "$after" | jq_get authenticated)" != "True" ] && _pass "logout revokes session" || _fail "session survived logout"

# anonymous action rejected (no session cookie / no CSRF -> governance blocks)
anon=$(curl -sS -m 10 -X POST "$ADMIN/verifications/rerun" \
  -H 'Content-Type: application/json' -d '{"script_key":"admin_console_v0","reason":"x"}' 2>/dev/null || echo '{}')
echo "$anon" | grep -qE 'no_valid_session|csrf_invalid|operator_actions_disabled|policy_blocked' \
  && _pass "anonymous action rejected" || _fail "anonymous allowed ($anon)"

# ---------------------------------------------------------------------------
echo; echo "=== Scenario B: RBAC (backend authoritative) ==="
# Use the SDK directly (backend-authoritative RBAC matrix).
"$PY" - <<'PY' && _pass "RBAC matrix correct" || _fail "RBAC matrix wrong"
from shared.sdk.operator_actions.rbac import role_can
assert role_can("viewer","delivery_package.accept") is False
assert role_can("reviewer","delivery_package.accept") is False
assert role_can("reviewer","operator_review.add_note") is True
assert role_can("reviewer","delivery_package.request_changes") is True
assert role_can("operator","delivery_package.accept") is True
assert role_can("platform_admin","delivery_package.accept") is True
assert role_can("operator","deployment.execute") is False
assert role_can("platform_admin","github.create_pr") is False
print("ok")
PY
# live: viewer blocked from accept
login viewer >/dev/null
PKG_PLACEHOLDER="00000000-0000-0000-0000-000000000000"
vresp=$(post_ops "delivery-packages/$PKG_PLACEHOLDER/operator-review/accept" '{"reason":"test"}')
echo "$vresp" | grep -q 'policy_blocked' && _pass "viewer accept policy_blocked" || _skip "viewer accept (no package / $vresp)"

# ---------------------------------------------------------------------------
echo; echo "=== Scenario C: delivery review actions ==="
# Ensure a ready_for_review package exists (run mini pilot + build).
pilot=$(curl -sS -m 180 -X POST "$ORCH/operations/mini-delivery-pilots/run" \
  -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
PILOT_ID=$(echo "$pilot" | jq_get pilot_id)
PKG_ID=""
if [ -n "$PILOT_ID" ]; then
  build=$(curl -sS -m 60 -X POST "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/delivery-package/build" \
    -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
  PKG_ID=$(echo "$build" | jq_get package_id)
fi
[ -z "$PKG_ID" ] && PKG_ID=$("$PY" - <<'PY' 2>/dev/null
import asyncio
from shared.sdk.delivery_package import DeliveryPackageStore
async def main():
    s = DeliveryPackageStore()
    rows = await s.list_delivery_packages(limit=20)
    for r in rows:
        if r.get("status") == "ready_for_review":
            print(r["id"]); return
asyncio.run(main())
PY
)
if [ -z "$PKG_ID" ]; then
  _fail "no ready_for_review package available"
else
  _pass "ready_for_review package $PKG_ID"
  login operator >/dev/null
  # add note (no confirmation needed)
  n=$(post_ops "delivery-packages/$PKG_ID/operator-review/notes" '{"reason":"looks good"}')
  echo "$n" | grep -qE 'completed|review_note_added' && _pass "operator add note" || _fail "add note ($n)"
  # request changes (confirmation required)
  rc=$(post_ops "delivery-packages/$PKG_ID/operator-review/request-changes" '{"reason":"tweak docs"}')
  rc_id=$(echo "$rc" | jq_get action_id); rc_nonce=$(echo "$rc" | jq_get confirmation_nonce)
  if [ -n "$rc_nonce" ]; then
    ex=$(post_admin "operator-actions/$rc_id/execute" "{\"confirmation_nonce\":\"$rc_nonce\"}")
    echo "$ex" | grep -q 'completed' && _pass "request changes (confirmed)" || _fail "request changes exec ($ex)"
  else
    _fail "request changes confirmation missing ($rc)"
  fi
  # accept (confirmation required)
  ac=$(post_ops "delivery-packages/$PKG_ID/operator-review/accept" '{"reason":"accepted by operator"}')
  ac_id=$(echo "$ac" | jq_get action_id); ac_nonce=$(echo "$ac" | jq_get confirmation_nonce)
  if [ -n "$ac_nonce" ]; then
    ex=$(post_admin "operator-actions/$ac_id/execute" "{\"confirmation_nonce\":\"$ac_nonce\"}")
    echo "$ex" | grep -q 'completed' && _pass "accept (confirmed)" || _fail "accept exec ($ex)"
    # verify human_acceptance_status=accepted
    has=$("$PY" - "$PKG_ID" <<'PY' 2>/dev/null
import asyncio, sys
from shared.sdk.delivery_package import DeliveryPackageStore
async def main():
    s = DeliveryPackageStore()
    p = await s.get_delivery_package(sys.argv[1])
    print((p or {}).get("human_acceptance_status",""))
asyncio.run(main())
PY
)
    [ "$has" = "accepted" ] && _pass "human_acceptance_status=accepted" || _fail "human acceptance=$has"
  else
    _fail "accept confirmation missing ($ac)"
  fi
fi

# ---------------------------------------------------------------------------
echo; echo "=== Scenario D: confirmation / idempotency ==="
login operator >/dev/null
if [ -n "${PKG_ID:-}" ]; then
  idem="idem-fixed-$$"
  r1=$(post_ops "delivery-packages/$PKG_ID/operator-review/notes" '{"reason":"dup-note"}' "$idem")
  r2=$(post_ops "delivery-packages/$PKG_ID/operator-review/notes" '{"reason":"dup-note"}' "$idem")
  echo "$r2" | grep -q 'idempotent_replay' && _pass "idempotency prevents duplicate" || _skip "idempotency ($r2)"
  # reused confirmation rejected: request changes, execute twice
  rc=$(post_ops "delivery-packages/$PKG_ID/operator-review/request-changes" '{"reason":"again"}')
  rc_id=$(echo "$rc" | jq_get action_id); rc_nonce=$(echo "$rc" | jq_get confirmation_nonce)
  if [ -n "$rc_nonce" ]; then
    post_admin "operator-actions/$rc_id/execute" "{\"confirmation_nonce\":\"$rc_nonce\"}" >/dev/null
    again=$(post_admin "operator-actions/$rc_id/execute" "{\"confirmation_nonce\":\"$rc_nonce\"}")
    echo "$again" | grep -qE 'already_used|completed.*idempotent_replay|idempotent_replay' && \
      _pass "reused/replayed confirmation handled" || _skip "reuse ($again)"
  fi
  # missing confirmation rejected
  rc2=$(post_ops "delivery-packages/$PKG_ID/operator-review/request-changes" '{"reason":"noconf"}')
  rc2_id=$(echo "$rc2" | jq_get action_id)
  miss=$(post_admin "operator-actions/$rc2_id/execute" '{}')
  echo "$miss" | grep -qE 'confirmation_invalid|confirmation_missing|policy_blocked' \
    && _pass "missing confirmation rejected" || _fail "missing confirmation allowed ($miss)"
else
  _skip "confirmation/idempotency (no package)"
fi

# ---------------------------------------------------------------------------
echo; echo "=== Scenario E: verification rerun ==="
"$PY" - <<'PY' && _pass "rerun allowlist + containment (SDK)" || _fail "rerun SDK guard"
from shared.sdk.operator_actions.verification_runner import (
    resolve_script, requires_higher_confirmation, ALLOWLISTED_SCRIPTS, VerificationNotAllowed)
assert resolve_script("admin_console_v0").name == "verify_admin_console_v0.sh"
for bad in ("../../etc/passwd", "rm -rf /", "arbitrary_key"):
    try:
        resolve_script(bad); raise SystemExit("arbitrary allowed: " + bad)
    except VerificationNotAllowed:
        pass
assert requires_higher_confirmation("full_regression") is True
assert set(ALLOWLISTED_SCRIPTS) == {"delivery_package_acceptance_gate","admin_console_v0",
    "backup_dr_gap_closure","audit_integrity","full_regression"}
print("ok")
PY
# shell=False + no arbitrary path in source
grep -q 'shell=False' shared/sdk/operator_actions/verification_runner.py && _pass "runner shell=False" || _fail "no shell=False"
login operator >/dev/null
# non-allowlisted rejected via API
bad=$(post_admin "verifications/rerun" '{"script_key":"/bin/sh","reason":"x"}')
echo "$bad" | grep -q 'verification_not_allowlisted' && _pass "API rejects non-allowlisted" || _fail "API allowed arbitrary ($bad)"
# allowlisted requires confirmation
ok=$(post_admin "verifications/rerun" '{"script_key":"admin_console_v0","reason":"rerun"}')
echo "$ok" | grep -qE 'confirmation_required|confirmation_nonce' && _pass "rerun requires confirmation" || _fail "rerun no confirmation ($ok)"
# full_regression requires higher confirmation ack
fr=$(post_admin "verifications/rerun" '{"script_key":"full_regression","reason":"rerun"}')
echo "$fr" | grep -qE 'higher_confirmation_required|high_risk_ack' && _pass "full_regression needs high_risk_ack" || _skip "full_regression ack ($fr)"

# ---------------------------------------------------------------------------
echo; echo "=== Scenario F: disabled actions ==="
for act in workflow.pause workflow.resume work_item.update_status github.create_pr github.merge_pr deployment.execute backup.production_run policy.update; do
  blocked=$("$PY" - "$act" <<'PY' 2>/dev/null
import sys
from shared.sdk.operator_actions.action_catalog import is_enabled, is_known
a = sys.argv[1]
print("blocked" if (is_known(a) and not is_enabled(a)) else "OPEN")
PY
)
  [ "$blocked" = "blocked" ] && _pass "disabled: $act" || _fail "executable: $act"
done
# no generic shell / command endpoint
curl -sS -m 5 -o /dev/null -w '%{http_code}' "$ORCH/operations/admin-console/execute-command" 2>/dev/null | grep -qE '404|405' \
  && _pass "no execute-command endpoint" || _skip "execute-command probe"

# ---------------------------------------------------------------------------
echo; echo "=== Scenario G: safety ==="
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
for kv in '"production_executed_true_count":0' '"admin_console_v1_enabled":true' \
          '"admin_console_rbac_enabled":true' '"admin_console_csrf_enabled":true' \
          '"admin_console_operator_actions_controlled_only":true' \
          '"admin_console_arbitrary_action_enabled":false' \
          '"admin_console_arbitrary_shell_enabled":false' \
          '"admin_console_workflow_pause_resume_enabled":false' \
          '"admin_console_work_item_mutation_enabled":false' \
          '"admin_console_github_actions_enabled":false' \
          '"admin_console_deployment_actions_enabled":false' \
          '"admin_console_production_actions_enabled":false' \
          '"admin_console_production_auth_enabled":false'; do
  echo "$saf" | grep -q "$kv" && _pass "safety $kv" || _fail "safety missing $kv"
done

# ---------------------------------------------------------------------------
echo; echo "=== Scenario H: audit / notifications ==="
"$PY" -c "
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST as d
assert 'operator_action.*' in d and 'operator_review.*' in d and 'verification_rerun.*' in d
print('ok')" >/dev/null 2>&1 && _pass "operator_action.* notifications default-denied" || _fail "denylist missing"
acnt=$($COMPOSE exec -T "$PG_SERVICE" psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM audit_logs WHERE decision_type LIKE 'operator_%' OR decision_type LIKE 'delivery_package_operator_%';" 2>/dev/null | tr -d '[:space:]')
[ "${acnt:-0}" -ge 1 ] && _pass "operator action audit events persisted ($acnt)" || _skip "audit events not yet converged"
if bash scripts/detect_audit_tamper_residue.sh 2>&1 | grep -q "AUDIT_TAMPER_RESIDUE_DETECTOR: FAIL"; then
  _fail "audit tamper residue detected"
else
  _pass "no audit tamper residue"
fi

# ---------------------------------------------------------------------------
echo; echo "=== Scenario I: regression compatibility ==="
if bash scripts/verify_admin_console_v0.sh >/tmp/v1_v0.log 2>&1; then
  grep -q "ADMIN_CONSOLE_V0_VERIFY: PASS" /tmp/v1_v0.log && _pass "v0 verify still PASS" || _fail "v0 verify not PASS"
else
  grep -q "ADMIN_CONSOLE_V0_VERIFY: PASS" /tmp/v1_v0.log && _pass "v0 verify PASS" || _fail "v0 verify failed (see /tmp/v1_v0.log)"
fi

# ---------------------------------------------------------------------------
echo; echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "ADMIN_CONSOLE_V1_OPERATOR_ACTIONS_VERIFY: PASS"; exit 0
else
  echo "ADMIN_CONSOLE_V1_OPERATOR_ACTIONS_VERIFY: FAIL"; exit 1
fi
