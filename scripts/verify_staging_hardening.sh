#!/usr/bin/env bash
# Stage 24 staging-readiness verifier.
#
# Runs every Stage 24 artefact in sequence and asserts the platform
# stays in a sandbox-safe posture. The script does NOT call the real
# GitHub / Discord / Slack / Telegram APIs and does NOT flip any of
# the controlled-real opt-in env vars.
#
# Run from the repository root.
set -uo pipefail

echo "### verify_staging_hardening: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=9

# 1. runtime config validator — local mode must PASS
echo
echo "=== 1. validate_runtime_config.sh --mode local ==="
if ./scripts/validate_runtime_config.sh --mode local 2>&1 | tee /tmp/rgv_local.$$ | tail -3; then
  if grep -q "RUNTIME_CONFIG_VALIDATION: PASS" /tmp/rgv_local.$$; then
    echo "  RUNTIME_CONFIG_LOCAL: PASS"
    checks=$((checks+1))
  else
    echo "  RUNTIME_CONFIG_LOCAL: FAIL"
  fi
fi
rm -f /tmp/rgv_local.$$

# 2. production safety gate
echo
echo "=== 2. production_safety_gate.sh ==="
if ./scripts/production_safety_gate.sh 2>&1 | tee /tmp/psg.$$ | tail -3; then
  if grep -q "PRODUCTION_SAFETY_GATE: PASS" /tmp/psg.$$; then
    echo "  PRODUCTION_SAFETY_GATE: PASS"
    checks=$((checks+1))
  else
    echo "  PRODUCTION_SAFETY_GATE: FAIL"
  fi
fi
rm -f /tmp/psg.$$

# 3. backup/restore smoke
echo
echo "=== 3. verify_backup_restore.sh ==="
if ./scripts/verify_backup_restore.sh 2>&1 | tee /tmp/bru.$$ | tail -5; then
  if grep -q "BACKUP_RESTORE_VERIFY: PASS" /tmp/bru.$$; then
    echo "  BACKUP_RESTORE_VERIFY: PASS"
    checks=$((checks+1))
  else
    echo "  BACKUP_RESTORE_VERIFY: FAIL"
  fi
fi
rm -f /tmp/bru.$$

# 4. runtime health snapshot
echo
echo "=== 4. runtime_health_snapshot.sh ==="
if ./scripts/runtime_health_snapshot.sh 2>&1 | tee /tmp/rhs.$$ | tail -3; then
  if grep -q "RUNTIME_HEALTH_SNAPSHOT_DONE: PASS" /tmp/rhs.$$; then
    echo "  RUNTIME_HEALTH_SNAPSHOT: PASS"
    checks=$((checks+1))
  else
    echo "  RUNTIME_HEALTH_SNAPSHOT: FAIL"
  fi
fi
rm -f /tmp/rhs.$$

# 5. runtime-health.log exists and has no token-shaped substring
echo
echo "=== 5. source/runtime-health.log no-token-leak check ==="
if [ -f source/runtime-health.log ]; then
  size=$(wc -c < source/runtime-health.log 2>/dev/null | tr -d '[:space:]')
  echo "  log bytes=$size"
  if grep -qiE 'ghp_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|Bearer [A-Za-z0-9._-]{30,}|Bot [A-Za-z0-9._-]{30,}|"token": "[A-Za-z0-9_.-]{10,}' source/runtime-health.log; then
    echo "  HEALTH_LOG_NO_TOKEN: FAIL"
  else
    echo "  HEALTH_LOG_NO_TOKEN: PASS"
    checks=$((checks+1))
  fi
else
  echo "  HEALTH_LOG_NO_TOKEN: FAIL (file missing)"
fi

# 6. docker-compose.staging.yml has no trust auth
echo
echo "=== 6. docker-compose.staging.yml no-trust-auth check ==="
if grep -q "POSTGRES_HOST_AUTH_METHOD: trust" infra/docker-compose/docker-compose.staging.yml 2>/dev/null; then
  echo "  STAGING_TEMPLATE_NO_TRUST_AUTH: FAIL"
else
  echo "  STAGING_TEMPLATE_NO_TRUST_AUTH: PASS"
  checks=$((checks+1))
fi

# 7. env examples carry placeholder marker only (no real secret bytes)
echo
echo "=== 7. env examples carry no real secret ==="
env_ok=1
for f in infra/runtime/env.schema.example infra/runtime/env.staging.example; do
  if grep -qE 'ghp_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|Bearer [A-Za-z0-9._-]{30,}|Bot [A-Za-z0-9._-]{30,}' "$f"; then
    echo "  $f: REAL_SECRET_DETECTED"
    env_ok=0
  fi
done
if [ "$env_ok" = "1" ]; then
  echo "  ENV_EXAMPLES_PLACEHOLDER_ONLY: PASS"
  checks=$((checks+1))
else
  echo "  ENV_EXAMPLES_PLACEHOLDER_ONLY: FAIL"
fi

# 8. production_executed=false (verified by safety gate too — repeated
#    here so the script remains self-contained).
echo
echo "=== 8. production_executed=false ==="
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
dep=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true_or_env_production = ${dep:-?}"
echo "  workflow_states.production_executed_true = ${wf:-?}"
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "  PRODUCTION_EXECUTED_FALSE: PASS"
  checks=$((checks+1))
else
  echo "  PRODUCTION_EXECUTED_FALSE: FAIL"
fi

# 9. SecretProvider redacts correctly (pure-Python self-test)
echo
echo "=== 9. SecretProvider redaction self-test ==="
if python3 -c "
import sys, os
sys.path.insert(0, '.')
from shared.sdk.secrets import EnvSecretProvider, redact, redact_mapping
p = EnvSecretProvider({'GITHUB_TOKEN': 'ghp_NEVER_LEAK_THIS_VALUE'})
ref = p.get_secret('GITHUB_TOKEN')
text = repr(ref) + ' ' + str(ref) + ' ' + redact(ref.reveal())
masked = redact_mapping({'GITHUB_TOKEN': 'x', 'plain': 'y'})
assert 'ghp_NEVER_LEAK_THIS_VALUE' not in text, 'token leaked through repr/str/redact'
assert masked['GITHUB_TOKEN'] == '***REDACTED***', 'redact_mapping missed GITHUB_TOKEN'
assert masked['plain'] == 'y', 'redact_mapping over-redacted'
print('SECRET_REDACTION: PASS')
" 2>&1; then
  checks=$((checks+1))
else
  echo "SECRET_REDACTION: FAIL"
fi

echo
echo "checks passed: $checks / $total"
if [ "$checks" -eq "$total" ]; then
  echo "STAGING_HARDENING_VERIFY: PASS"
else
  echo "STAGING_HARDENING_VERIFY: CHECK"
fi
echo
echo "VERIFY_STAGING_HARDENING_DONE"
