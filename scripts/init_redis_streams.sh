#!/usr/bin/env bash
# Initialize Redis Streams consumer groups for the AI Agents SWD Platform.
# Idempotent: existing groups are reported and do not fail the script.
# Run from the repository root.
set -euo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"
REDIS="$COMPOSE exec -T redis redis-cli"

PAIRS=(
  "stream.tasks orchestrator-group"
  "stream.tasks intake-agent-group"
  "stream.requirements requirement-agent-group"
  "stream.development development-agent-group"
  "stream.qa qa-agent-group"
  "stream.deployments devops-agent-group"
  "stream.devops orchestrator-workflow-group"
  "stream.development orchestrator-workflow-group"
  "stream.qa orchestrator-workflow-group"
  "stream.deployments orchestrator-workflow-group"
  "stream.approvals approval-group"
  "stream.audit audit-group"
  "stream.notifications notification-group"
  "stream.incidents incident-group"
  "stream.deadletter deadletter-group"
)

echo "=== Redis Streams consumer-group initialization ==="
created=0
existed=0
for pair in "${PAIRS[@]}"; do
  stream="${pair%% *}"
  group="${pair##* }"
  out="$($REDIS XGROUP CREATE "$stream" "$group" '$' MKSTREAM 2>&1 || true)"
  if printf '%s' "$out" | grep -q "OK"; then
    echo "  created : $stream / $group"
    created=$((created + 1))
  elif printf '%s' "$out" | grep -q "BUSYGROUP"; then
    echo "  exists  : $stream / $group"
    existed=$((existed + 1))
  else
    echo "  ERROR   : $stream / $group -> $out"
    exit 1
  fi
done
echo "summary: ${created} created, ${existed} already existed, ${#PAIRS[@]} total"
echo "REDIS_STREAMS_INIT_DONE"
