#!/usr/bin/env bash
# Stage 24 runtime health snapshot.
#
# Writes a flat, human-readable summary of the live cluster to
# ``source/runtime-health.log``. The snapshot is intentionally lossy —
# only counts and status booleans — so the file can be re-generated
# safely and never picks up a secret.
#
# The Stage 24 verify script (verify_staging_hardening.sh) greps the
# generated log to assert no token-shaped substring leaked in.
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose/docker-compose.yml}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
PROM="${PROMETHEUS_URL:-http://localhost:9090}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-aiagents}"

out="source/runtime-health.log"
mkdir -p "$(dirname "$out")"
: > "$out"

{
  echo "### runtime_health_snapshot generated $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo
  echo "## git HEAD"
  git log -1 --pretty='%h %s' 2>/dev/null || echo "(no git context)"
  echo
  echo "## docker compose ps"
  docker compose -f "$COMPOSE_FILE" ps --format "table {{.Service}}\t{{.Status}}" 2>/dev/null \
    || echo "(docker compose unavailable)"
  echo
  echo "## /operations/summary"
  curl -sS -m 5 "$ORCH/operations/summary" 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Print only the high-level counters; never echo any secret-shaped field.
out = {
  'services_summary':     data.get('services_summary', {}),
  'workflows_summary':    data.get('workflows_summary', {}),
  'agents_summary':       data.get('agents_summary', {}),
  'incidents_summary':    data.get('incidents_summary', {}),
  'dlq_summary':          data.get('dlq_summary', {}),
  'github_summary':       {k: v for k, v in (data.get('github_summary') or {}).items() if k != 'has_token' or isinstance(v, bool)},
  'audit_summary':        data.get('audit_summary', {}),
  'production_safety':    data.get('production_safety', {}),
  'notification_delivery_summary': data.get('notification_delivery_summary', {}),
}
print(json.dumps(out, indent=2, sort_keys=True))
" 2>/dev/null || echo "(operations summary unavailable)"
  echo
  echo "## /operations/safety"
  curl -sS -m 5 "$ORCH/operations/safety" 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Boolean-only mirror — no token value, no warning string can carry a secret.
keep = {
  'production_executed_true_count', 'workflow_production_executed_true_count',
  'deployment_environment_production_count',
  'github_has_token', 'github_default_dry_run',
  'real_github_test_enabled', 'github_test_repo_configured',
  'github_external_write_enabled',
  'discord_has_token', 'discord_real_test_enabled',
  'discord_test_channel_configured', 'discord_external_send_enabled',
  'alertmanager_receivers', 'external_alert_receivers_present',
  'result', 'warnings'
}
out = {k: v for k, v in data.items() if k in keep}
print(json.dumps(out, indent=2, sort_keys=True))
" 2>/dev/null || echo "(safety unavailable)"
  echo
  echo "## Prometheus targets up/down"
  curl -sS -m 5 "$PROM/api/v1/targets" 2>/dev/null \
    | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    targets = data.get('data', {}).get('activeTargets', []) or []
    up = sum(1 for t in targets if t.get('health') == 'up')
    down = sum(1 for t in targets if t.get('health') != 'up')
    print(f'targets_total={len(targets)} up={up} down={down}')
except Exception as e:
    print(f'(prom targets unavailable: {e})')
" 2>/dev/null || echo "(prom unavailable)"
  echo
  echo "## production_executed counters (Postgres)"
  dep=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
    2>/dev/null | tr -d '[:space:]')
  wf=$(docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
    2>/dev/null | tr -d '[:space:]')
  echo "deployment_records.production_executed_true_or_env_production=${dep:-?}"
  echo "workflow_states.production_executed_true=${wf:-?}"
  echo
  echo "## Stream lag (orchestrator /operations/streams)"
  curl -sS -m 5 "$ORCH/operations/streams" 2>/dev/null \
    | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for s in data.get('streams', []) or []:
        print(f\"stream={s.get('name'):<32} length={s.get('length',0):<6} pending={s.get('pending',0):<4} lag={s.get('lag',0):<4} status={s.get('status','?')}\")
except Exception as e:
    print(f'(streams unavailable: {e})')
" 2>/dev/null || echo "(streams unavailable)"
  echo
  echo "## open incidents"
  curl -sS -m 5 "$ORCH/operations/incidents?status=open" 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"open_incidents={data.get('open_count', 0)} acknowledged={data.get('acknowledged_count', 0)}\")
" 2>/dev/null || echo "(incidents unavailable)"
  echo
  echo "### runtime_health_snapshot end"
} > "$out" 2>&1

echo "runtime_health_snapshot written: $out (bytes=$(wc -c < "$out" 2>/dev/null | tr -d '[:space:]'))"
echo "RUNTIME_HEALTH_SNAPSHOT_DONE: PASS"
