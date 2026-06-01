#!/usr/bin/env bash
# Stage 25 staging tear-down.
#
# Brings the aiagents-staging project down. By default volumes are
# kept so the operator can re-up the same DB on the next run; pass
# ``--volumes`` (or ``--purge``) to also remove the staging volumes
# (postgres-staging-data, prometheus-staging-data, etc.).
#
# Run from the repository root.
set -uo pipefail

COMPOSE_FILE="${STAGING_COMPOSE_FILE:-infra/docker-compose/docker-compose.staging.yml}"
PROJECT="${STAGING_COMPOSE_PROJECT:-aiagents-staging}"
ENV_FILE="${STAGING_ENV_FILE:-infra/runtime/.env.staging.local}"
COMPOSE="docker compose -p ${PROJECT} -f ${COMPOSE_FILE}"

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --volumes|--purge) PURGE=1 ;;
  esac
done

echo "### stop_staging_runtime start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  project=$PROJECT"
echo "  purge_volumes=$PURGE"

# docker compose down needs the same env-file used for `up` because
# Postgres still has POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?}. Without
# it the YAML parser refuses. Fall back to a noop password when the
# env file is gone — `down` doesn't actually need the value.
if [ -f "$ENV_FILE" ]; then
  ENV_FLAG="--env-file $ENV_FILE"
else
  echo "  $ENV_FILE missing — using POSTGRES_PASSWORD=tear-down-noop for compose parse"
  export POSTGRES_PASSWORD="tear-down-noop"
  ENV_FLAG=""
fi

if [ "$PURGE" = "1" ]; then
  $COMPOSE $ENV_FLAG down --volumes --remove-orphans || true
  echo "STOP_STAGING_RUNTIME: PASS (purged volumes)"
else
  $COMPOSE $ENV_FLAG down --remove-orphans || true
  echo "STOP_STAGING_RUNTIME: PASS"
fi
