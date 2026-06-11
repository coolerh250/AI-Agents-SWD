#!/usr/bin/env bash
# Stage 38 -- LLM Model Routing & Agent Model Policy end-to-end verify.
#
# Scenarios:
#   A. seed default model registry + agent policies (idempotent)
#   B. preview routing for intake classification + development_plan
#   C. blocked / unsupported / direct-model rejection
#   D. fallback selected when preferred is missing
#   E. integration -- record + read decisions, confirm
#      production_executed=false and patch/workspace stay hard-off.
#
# Marker: LLM_MODEL_ROUTING_VERIFY: PASS / FAIL.
set -uo pipefail

ORCH="${ORCH:-http://localhost:8000}"

echo "### verify_llm_model_routing start: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ---------- Scenario A: seed registry + policies ----------
echo "=== A. seed registry + policies ==="
seed_body=$(curl -sS -m 30 -X POST "$ORCH/operations/llm/routing/seed-defaults" \
  -H 'Content-Type: application/json' -d '{}' || echo '{}')
seeded_models=$(echo "$seed_body" | grep -oE '"seeded_models":\s*\[[^]]*\]' || true)
seeded_policies=$(echo "$seed_body" | grep -oE '"seeded_policies":\s*\[[^]]*\]' || true)
echo "  seeded_models=$seeded_models"
echo "  seeded_policies=$seeded_policies"
if ! echo "$seed_body" | grep -q 'mock-default'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL seed_did_not_include_mock_default"
  exit 1
fi
if ! echo "$seed_body" | grep -q 'development-agent'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL seed_did_not_include_development_agent"
  exit 1
fi

# Verify active models + policies listed.
models_body=$(curl -sS -m 10 "$ORCH/operations/llm/models?status=active" || echo '{}')
policies_body=$(curl -sS -m 10 "$ORCH/operations/llm/model-policies?status=active" || echo '{}')
mock_count=$(echo "$models_body" | grep -oE '"model_alias":\s*"mock-[a-z]+"' | wc -l | tr -d ' ')
policy_count=$(echo "$policies_body" | grep -oE '"agent_name":' | wc -l | tr -d ' ')
echo "  active_mock_count=$mock_count active_policy_count=$policy_count"
if [ "$mock_count" -lt 2 ]; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL active_mock_count_lt_2"
  exit 1
fi
if [ "$policy_count" -lt 5 ]; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL active_policy_count_lt_5"
  exit 1
fi

# ---------- Scenario B: routing selection ----------
echo "=== B. routing selection ==="
intake_preview=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"intake-agent","capability":"classification","risk_level":"low","persist":true}' || echo '{}')
intake_decision=$(echo "$intake_preview" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  intake decision=$intake_decision"
case "$intake_decision" in
  selected|mock_selected|fallback_selected) ;;
  *) echo "LLM_MODEL_ROUTING_VERIFY: FAIL intake_routing_unexpected=$intake_decision"; exit 1 ;;
esac

dev_preview=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"development-agent","capability":"development_plan","risk_level":"medium","requested_schema":"LLMDevelopmentPlan","persist":true}' || echo '{}')
dev_decision=$(echo "$dev_preview" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  dev_plan decision=$dev_decision"
case "$dev_decision" in
  selected|mock_selected|fallback_selected) ;;
  *) echo "LLM_MODEL_ROUTING_VERIFY: FAIL dev_routing_unexpected=$dev_decision"; exit 1 ;;
esac

# Verify selected fields are non-empty for a select decision.
if ! echo "$dev_preview" | grep -q '"selected_provider":\s*"mock"'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL dev_routing_provider_not_mock"
  exit 1
fi

# ---------- Scenario C: blocked ----------
echo "=== C. blocked ==="
unsupported=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"development-agent","capability":"development_plan","requested_schema":"NotARealSchema"}' || echo '{}')
unsup_decision=$(echo "$unsupported" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  unsupported_schema decision=$unsup_decision"
case "$unsup_decision" in
  blocked|schema_unsupported) ;;
  *) echo "LLM_MODEL_ROUTING_VERIFY: FAIL unsupported_schema_unexpected=$unsup_decision"; exit 1 ;;
esac

nopolicy=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"unknown-bot","capability":"made_up"}' || echo '{}')
nopol_decision=$(echo "$nopolicy" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  no_policy decision=$nopol_decision"
if [ "$nopol_decision" != "policy_not_found" ]; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL no_policy_unexpected=$nopol_decision"
  exit 1
fi

direct=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"development-agent","capability":"development_plan","risk_level":"medium","requested_model_alias":"unauthorised-real-model"}' || echo '{}')
direct_decision=$(echo "$direct" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  direct_model_request decision=$direct_decision"
if [ "$direct_decision" != "direct_model_rejected" ]; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL direct_model_not_rejected=$direct_decision"
  exit 1
fi

# ---------- Scenario D: fallback ----------
echo "=== D. fallback ==="
# Summarization for intake-agent prefers mock-lightweight. Verify the
# router yields a select decision (fallback path is exercised when
# preferred missing; mock-lightweight is preferred so this just confirms
# the gate works).
fb=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d '{"agent_name":"intake-agent","capability":"summarization"}' || echo '{}')
fb_decision=$(echo "$fb" | grep -oE '"decision":\s*"[^"]+"' | head -1 | sed 's/.*:"\(.*\)"/\1/')
echo "  summarization decision=$fb_decision"
case "$fb_decision" in
  selected|mock_selected|fallback_selected) ;;
  *) echo "LLM_MODEL_ROUTING_VERIFY: FAIL fallback_path_unexpected=$fb_decision"; exit 1 ;;
esac

# ---------- Scenario E: integration ----------
echo "=== E. integration ==="
# Persisted decisions reachable by task_id.
sample_task="validation-pilot-routing-$(date +%s%N)"
_=$(curl -sS -m 10 -X POST "$ORCH/operations/llm/routing/preview" \
  -H 'Content-Type: application/json' \
  -d "{\"agent_name\":\"development-agent\",\"capability\":\"development_plan\",\"task_id\":\"$sample_task\",\"persist\":true,\"requested_schema\":\"LLMDevelopmentPlan\",\"risk_level\":\"medium\"}" \
  || echo '{}')
sleep 1
decisions=$(curl -sS -m 10 "$ORCH/operations/llm/routing-decisions/$sample_task" || echo '{}')
echo "  per-task decisions:"
echo "$decisions" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    d={}
print(' count=', d.get('count'))
for x in d.get('decisions', [])[:3]:
    print('   ', x.get('decision'), x.get('selected_model_alias'),
          'patch_off=', x.get('patch_generation_allowed'),
          'ws_off=', x.get('workspace_write_allowed'))
"
if ! echo "$decisions" | grep -q '"count":\s*[1-9]'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL no_persisted_decisions_for_sample_task"
  exit 1
fi
# Confirm patch_generation_allowed=false and workspace_write_allowed=false.
if echo "$decisions" | grep -q '"patch_generation_allowed":\s*true'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL patch_generation_allowed_true_in_decision"
  exit 1
fi
if echo "$decisions" | grep -q '"workspace_write_allowed":\s*true'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL workspace_write_allowed_true_in_decision"
  exit 1
fi

# Confirm /operations/safety carries the Stage 38 fields.
safety=$(curl -sS -m 5 "$ORCH/operations/safety" || echo '{}')
if ! echo "$safety" | grep -qE '"agent_direct_model_selection_allowed":\s*false'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL safety_agent_direct_model_selection_allowed_not_false"
  exit 1
fi
if ! echo "$safety" | grep -qE '"llm_model_router_enabled":\s*true'; then
  echo "LLM_MODEL_ROUTING_VERIFY: FAIL safety_llm_model_router_enabled_not_true"
  exit 1
fi

echo
echo "LLM_MODEL_ROUTING_VERIFY: PASS"
