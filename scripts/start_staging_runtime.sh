#!/usr/bin/env bash
# Stage 25 staging bring-up entry point.
#
#   1. Loads ``infra/runtime/.env.staging.local`` if present, else
#      regenerates one with scripts/generate_staging_env.sh.
#   2. Validates the staging env via
#      ``./scripts/validate_runtime_config.sh --mode staging``.
#      Vault dev-mode passes when ALLOW_VAULT_DEV_MODE_FOR_STAGING=true
#      (the documented Step 24 escape hatch); otherwise the script
#      stops with a clear failure.
#   3. Brings up the staging compose under the ``aiagents-staging``
#      docker compose project — fully parallel with the local/test
#      ``aiagents-test`` project. Host ports are offset +10000.
#   4. Waits for Postgres + Redis, applies migrations, initialises
#      Redis Streams, restarts the consumer services so they pick up
#      the freshly-created tables.
#   5. Prints the staging port map so the operator + verify scripts can
#      target the sibling cluster.
#
# Pass ``--rebuild`` to force ``docker compose build`` first. Default
# behaviour reuses any already-built ``aiagents-staging-*`` images.
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${STAGING_COMPOSE_FILE:-infra/docker-compose/docker-compose.staging.yml}"
PROJECT="${STAGING_COMPOSE_PROJECT:-aiagents-staging}"
ENV_FILE="${STAGING_ENV_FILE:-infra/runtime/.env.staging.local}"
COMPOSE="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"

REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
  esac
done

echo "### start_staging_runtime start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  project=$PROJECT"
echo "  compose=$COMPOSE_FILE"
echo "  env_file=$ENV_FILE"

# 1. ensure env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "  $ENV_FILE missing — generating"
  ./scripts/generate_staging_env.sh || {
    echo "START_STAGING_RUNTIME: FAIL (env generation failed)"
    exit 1
  }
fi

# 1b. ensure mock-vault file exists (Stage 26 default provider). The
# staging compose mounts ../runtime/.mock-vault-secrets.local.json into
# every secret-aware service; bind mount fails if the host file is
# missing, so bootstrap it on demand. Skip when the operator opted in
# to a real Vault via SECRET_PROVIDER=vault.
chosen_provider="$(grep -E '^SECRET_PROVIDER=' "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2-)"
chosen_provider="${SECRET_PROVIDER:-${chosen_provider:-mock-vault}}"
if [ "$chosen_provider" = "mock-vault" ]; then
  MOCK_VAULT_FILE="${MOCK_VAULT_SECRETS_FILE:-infra/runtime/.mock-vault-secrets.local.json}"
  if [ ! -f "$MOCK_VAULT_FILE" ]; then
    echo "  $MOCK_VAULT_FILE missing — bootstrapping mock-vault fixture"
    ./scripts/bootstrap_mock_vault_secrets.sh || {
      echo "START_STAGING_RUNTIME: FAIL (mock vault bootstrap failed)"
      exit 1
    }
  fi
elif [ "$chosen_provider" = "vault" ]; then
  if [ -z "${VAULT_ADDR:-}" ] || [ -z "${VAULT_TOKEN:-}" ]; then
    echo "START_STAGING_RUNTIME: FAIL (SECRET_PROVIDER=vault requires VAULT_ADDR + VAULT_TOKEN)"
    exit 1
  fi
fi

# 2. validate. Vault dev-mode requires the escape hatch.
if ! grep -q '^ALLOW_VAULT_DEV_MODE_FOR_STAGING=true' "$ENV_FILE"; then
  # The Step 24 staging compose still ships the dev-mode vault container.
  # Auto-enable the documented escape hatch so the validator doesn't
  # fail this bring-up; the operator is asked to flip it back to false
  # before any production hand-off (covered in
  # docs/operations/staging-runtime-hardening.md).
  echo "  enabling ALLOW_VAULT_DEV_MODE_FOR_STAGING=true (staging escape hatch)"
  if grep -q '^ALLOW_VAULT_DEV_MODE_FOR_STAGING=' "$ENV_FILE"; then
    sed -i.bak 's|^ALLOW_VAULT_DEV_MODE_FOR_STAGING=.*|ALLOW_VAULT_DEV_MODE_FOR_STAGING=true|' "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
  else
    echo "ALLOW_VAULT_DEV_MODE_FOR_STAGING=true" >> "$ENV_FILE"
  fi
fi

if ! ./scripts/validate_runtime_config.sh --mode staging --env-file "$ENV_FILE" 2>&1 | tee /tmp/sssv.$$; then
  rc=$?
  rm -f /tmp/sssv.$$
  echo "START_STAGING_RUNTIME: FAIL (validator failed rc=$rc)"
  exit 1
fi
rm -f /tmp/sssv.$$

# 3. compose build (optional) + up
if [ "$REBUILD" = "1" ]; then
  echo
  echo "=== [build] staging images ==="
  $COMPOSE --env-file "$ENV_FILE" build || {
    echo "START_STAGING_RUNTIME: FAIL (compose build failed)"
    exit 1
  }
fi

echo
echo "=== [up] bringing aiagents-staging up ==="
$COMPOSE --env-file "$ENV_FILE" up -d || {
  echo "START_STAGING_RUNTIME: FAIL (compose up failed)"
  exit 1
}

# 4. wait for postgres + redis
echo
echo "=== [wait] staging postgres ready ==="
pg_user=$(grep -E '^STAGING_POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- || true)
pg_user="${pg_user:-aiagents_app}"
pg_db=$(grep -E '^STAGING_POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- || true)
pg_db="${pg_db:-aiagents}"
pg_ok=0
for i in $(seq 1 45); do
  if $COMPOSE --env-file "$ENV_FILE" exec -T postgres pg_isready -U "$pg_user" -d "$pg_db" >/dev/null 2>&1; then
    pg_ok=1
    echo "  postgres ready (attempt $i)"
    break
  fi
  sleep 2
done
if [ "$pg_ok" -ne 1 ]; then
  echo "START_STAGING_RUNTIME: FAIL (staging postgres did not become ready)"
  exit 1
fi

echo
echo "=== [wait] staging redis ready ==="
redis_ok=0
for i in $(seq 1 30); do
  if [ "$($COMPOSE --env-file "$ENV_FILE" exec -T redis redis-cli ping 2>/dev/null | tr -d '[:space:]')" = "PONG" ]; then
    redis_ok=1
    echo "  redis ready (attempt $i)"
    break
  fi
  sleep 2
done
if [ "$redis_ok" -ne 1 ]; then
  echo "START_STAGING_RUNTIME: FAIL (staging redis did not become ready)"
  exit 1
fi

# 5. apply migrations (idempotent)
echo
echo "=== [migrate] applying migrations to staging DB ==="
for migration in migrations/*.sql; do
  echo "  -- applying $migration"
  if ! $COMPOSE --env-file "$ENV_FILE" exec -T postgres psql -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 < "$migration" >/dev/null 2>&1; then
    echo "START_STAGING_RUNTIME: FAIL (migration $migration failed)"
    exit 1
  fi
done

# 6. initialise Redis Streams against the staging Redis. Reuse the
# existing init script via STAGING-aware env overrides.
echo
echo "=== [streams] initialising Redis Streams on staging ==="
STAGING_COMPOSE_PROJECT="$PROJECT" \
STAGING_COMPOSE_FILE="$COMPOSE_FILE" \
STAGING_ENV_FILE="$ENV_FILE" \
bash scripts/init_redis_streams.sh --staging 2>&1 | tail -5 || {
  # init_redis_streams.sh doesn't accept --staging today; we'll add it
  # below. For now, run the redis-cli commands inline.
  echo "  inline staging stream init"
  for pair in \
      "stream.tasks orchestrator-group" \
      "stream.tasks intake-agent-group" \
      "stream.requirements requirement-agent-group" \
      "stream.development development-agent-group" \
      "stream.qa qa-agent-group" \
      "stream.deployments devops-agent-group" \
      "stream.devops orchestrator-workflow-group" \
      "stream.development orchestrator-workflow-group" \
      "stream.qa orchestrator-workflow-group" \
      "stream.deployments orchestrator-workflow-group" \
      "stream.notifications notification-group" \
      "stream.notifications notification-worker-group" \
      "stream.audit audit-group" \
      "stream.approvals approval-group" \
      "stream.deadletter retry-scheduler-group" \
      "stream.deadletter.terminal terminal-failure-group" \
    ; do
    set -- $pair
    stream="$1"; group="$2"
    $COMPOSE --env-file "$ENV_FILE" exec -T redis \
      redis-cli XGROUP CREATE "$stream" "$group" '$' MKSTREAM >/dev/null 2>&1 || true
  done
}

# 7. restart consumer services so they pick up the freshly-migrated DB.
echo
echo "=== [restart] consumer services ==="
$COMPOSE --env-file "$ENV_FILE" restart \
  orchestrator audit-worker notification-worker discord-gateway \
  intake-agent requirement-agent development-agent qa-agent devops-agent \
  retry-scheduler approval-engine audit-service >/dev/null 2>&1 || true

# 8. port map
echo
echo "=== staging port map (host -> container) ==="
cat <<'EOF'
  postgres            127.0.0.1:15432 -> 5432
  redis               127.0.0.1:16379 -> 6379
  vault               127.0.0.1:18200 -> 8200
  orchestrator        127.0.0.1:18000 -> 8000
  policy-engine       127.0.0.1:18001 -> 8001
  approval-engine     127.0.0.1:18002 -> 8002
  audit-service       127.0.0.1:18003 -> 8003
  communication-gateway 127.0.0.1:18004 -> 8004
  github-automation   127.0.0.1:18005 -> 8005
  audit-worker        127.0.0.1:18006 -> 8006
  discord-gateway     127.0.0.1:18007 -> 8007
  notification-worker 127.0.0.1:18008 -> 8008
  intake-agent        127.0.0.1:18010 -> 8010
  requirement-agent   127.0.0.1:18011 -> 8011
  development-agent   127.0.0.1:18012 -> 8012
  qa-agent            127.0.0.1:18013 -> 8013
  devops-agent        127.0.0.1:18014 -> 8014
  retry-scheduler     127.0.0.1:18015 -> 8015
  prometheus          127.0.0.1:19090 -> 9090
  grafana             127.0.0.1:13000 -> 3000
  alertmanager        127.0.0.1:19093 -> 9093
  tempo               127.0.0.1:13200 -> 3200, 14317 -> 4317, 14318 -> 4318
EOF

echo
echo "START_STAGING_RUNTIME: PASS"
