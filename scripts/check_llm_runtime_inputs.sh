#!/usr/bin/env bash
# Stage 35 -- LLM runtime inputs check.
#
# Presence + length only -- values are NEVER printed. The script
# emits PASS / BLOCKED / SKIPPED markers based on which subset of
# the inputs the operator provided. The defaults assume mock + no
# real LLM, so a fresh test cluster passes with SKIPPED.

set -uo pipefail

ok() { echo "$1"; }
present() {
  local name="$1"
  local value="${!name:-}"
  if [ -n "$value" ]; then
    printf "  %s: present (len=%d)\n" "$name" "${#value}"
    return 0
  else
    printf "  %s: ABSENT\n" "$name"
    return 1
  fi
}
present_bool_true() {
  local name="$1"
  local value="${!name:-}"
  if [ "${value,,}" = "true" ]; then
    printf "  %s: true\n" "$name"
    return 0
  else
    printf "  %s: %s\n" "$name" "${value:-<unset>}"
    return 1
  fi
}

echo "### check_llm_runtime_inputs: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== Required ==="
present LLM_PROVIDER || true
have_run_real=0
have_network_call=0
present_bool_true RUN_REAL_LLM_TEST  && have_run_real=1 || true
present_bool_true ENABLE_REAL_LLM_NETWORK_CALL && have_network_call=1 || true

echo
echo "=== Provider keys (presence only -- value NEVER printed) ==="
have_openai=0
have_anthropic=0
present OPENAI_API_KEY  && have_openai=1 || true
present OPENAI_MODEL  || true
present ANTHROPIC_API_KEY && have_anthropic=1 || true
present ANTHROPIC_MODEL || true

echo
echo "=== Budget caps ==="
have_caps=0
for v in LLM_MAX_TOKENS_PER_TASK LLM_MAX_COST_PER_TASK_USD \
         LLM_MAX_COST_PER_DAY_USD LLM_MAX_COST_PER_MONTH_USD \
         LLM_BUDGET_POLICY_MODE; do
  present "$v" && have_caps=$((have_caps + 1)) || true
done

echo
provider_lower="$(echo "${LLM_PROVIDER:-mock}" | tr 'A-Z' 'a-z')"
echo "provider_lower: $provider_lower"
echo "have_run_real_test: $have_run_real"
echo "have_network_call: $have_network_call"
echo "have_openai_key: $have_openai"
echo "have_anthropic_key: $have_anthropic"
echo "have_budget_caps: $have_caps / 5"

echo

case "$provider_lower" in
  external_openai)
    if [ "$have_run_real" = "1" ] && [ "$have_network_call" = "1" ] \
       && [ "$have_openai" = "1" ]; then
      ok "REAL_LLM_INPUTS: PRESENT (provider=external_openai)"
    else
      ok "REAL_LLM_TEST_SKIPPED: PASS (provider=external_openai but inputs incomplete)"
    fi
    ;;
  external_anthropic)
    if [ "$have_run_real" = "1" ] && [ "$have_network_call" = "1" ] \
       && [ "$have_anthropic" = "1" ]; then
      ok "REAL_LLM_INPUTS: PRESENT (provider=external_anthropic)"
    else
      ok "REAL_LLM_TEST_SKIPPED: PASS (provider=external_anthropic but inputs incomplete)"
    fi
    ;;
  external_openai_placeholder|external_anthropic_placeholder)
    ok "REAL_LLM_TEST_SKIPPED: PASS (placeholder provider; real wire path disabled)"
    ;;
  mock|disabled|"")
    ok "REAL_LLM_TEST_SKIPPED: PASS (provider=$provider_lower; no real LLM gate)"
    ;;
  *)
    ok "REAL_LLM_INPUTS: BLOCKED (unknown provider=$provider_lower)"
    ;;
esac

echo "CHECK_LLM_RUNTIME_INPUTS_DONE"
