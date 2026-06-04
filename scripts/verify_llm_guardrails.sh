#!/usr/bin/env bash
# Stage 30 -- LLM provider + safety guardrails verifier.
#
# Five checks on the local/test stack (no real LLM, no real GitHub,
# no real Discord, no production deploy):
#
#   1) LLM_PROVIDER defaults to ``mock`` when the env var is unset.
#   2) Mock provider produces a deterministic, policy-clean proposal.
#   3) Mock provider's "denied path" trip produces a policy block.
#   4) /operations/safety exposes the LLM rail fields without leaking
#      the API key value.
#   5) Real LLM call is skipped by default (RUN_REAL_LLM_TEST=false).
#
# REAL_LLM_TEST_SKIPPED: PASS is the expected default outcome.
set -uo pipefail

ORCH="${ORCH_URL:-http://localhost:8000}"

echo "### verify_llm_guardrails: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=5
fail() { echo "  $1: FAIL"; }
pass() { echo "  $1: PASS"; checks=$((checks+1)); }

# 1. LLM_PROVIDER default
echo
echo "=== Provider default ==="
default_provider=$(curl -sS -m 10 "${ORCH}/operations/safety" \
  | python3 -c "import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('llm_provider', ''))
except Exception:
    print('')")
if [ "$default_provider" = "mock" ]; then
  pass "LLM_PROVIDER_DEFAULT_MOCK"
else
  fail "LLM_PROVIDER_DEFAULT_MOCK (got: $default_provider)"
fi

# 2. Mock provider policy-clean proposal (in-process)
echo
echo "=== Mock provider clean proposal ==="
clean_ok=$(python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import MockLLMProvider, apply_llm_safety_policy
p = MockLLMProvider()
prop = p.generate_patch_proposal(task_id='verify-clean', description='please add /healthz API')
res = apply_llm_safety_policy(prop)
print('PASS' if res['allowed'] and prop.requires_human_review else 'FAIL')
")
if [ "$clean_ok" = "PASS" ]; then
  pass "MOCK_PROVIDER_CLEAN"
else
  fail "MOCK_PROVIDER_CLEAN"
fi

# 3. Mock provider policy block
echo
echo "=== Mock provider policy block ==="
block_ok=$(python3 -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import MockLLMProvider, apply_llm_safety_policy
p = MockLLMProvider()
prop = p.generate_patch_proposal(task_id='verify-deny', description='please denied path test')
res = apply_llm_safety_policy(prop)
rules = {v['rule'] for v in res['violations']}
ok = (res['allowed'] is False) and ('path_blocked' in rules)
print('PASS' if ok else 'FAIL')
")
if [ "$block_ok" = "PASS" ]; then
  pass "MOCK_PROVIDER_POLICY_BLOCK"
else
  fail "MOCK_PROVIDER_POLICY_BLOCK"
fi

# 4. /operations/safety LLM fields
echo
echo "=== Safety endpoint LLM fields ==="
safety_body=$(curl -sS -m 10 "${ORCH}/operations/safety" || echo '{}')
safety_ok=$(echo "$safety_body" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    have_fields = all(k in d for k in (
        'llm_provider',
        'llm_real_enabled',
        'llm_external_call_enabled',
        'llm_policy_enforced',
        'llm_requires_human_review',
    ))
    no_leak = 'LLM_API_KEY' not in d and 'OPENAI_API_KEY' not in d
    print('PASS' if have_fields and no_leak else 'FAIL')
except Exception as e:
    print('FAIL')
")
if [ "$safety_ok" = "PASS" ]; then
  pass "SAFETY_LLM_FIELDS"
else
  fail "SAFETY_LLM_FIELDS"
fi

# 5. Real LLM test skipped (default)
echo
echo "=== Real LLM test skipped ==="
real_enabled=$(echo "$safety_body" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('true' if d.get('llm_real_enabled') is True else 'false')
except Exception:
    print('false')")
if [ "$real_enabled" = "false" ]; then
  pass "REAL_LLM_TEST_SKIPPED"
  echo "  REAL_LLM_TEST_SKIPPED: PASS"
else
  fail "REAL_LLM_TEST_SKIPPED"
fi

echo
echo "passed ${checks}/${total}"
if [ "$checks" -ge "$total" ]; then
  echo "LLM_GUARDRAILS_VERIFY: PASS"
  exit 0
else
  echo "LLM_GUARDRAILS_VERIFY: FAIL"
  exit 1
fi
