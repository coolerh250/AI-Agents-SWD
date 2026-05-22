#!/usr/bin/env bash
# Start the local/test Docker Compose runtime, apply the PostgreSQL migration,
# and initialize Redis Streams. Idempotent. Run from the repository root.
set -euo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### init_local_runtime start: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== [1] start docker compose runtime ==="
$COMPOSE up -d

echo
echo "=== [2] wait for PostgreSQL ==="
pg_ok=0
for i in $(seq 1 30); do
  if $COMPOSE exec -T postgres pg_isready -U postgres -d aiagents >/dev/null 2>&1; then
    pg_ok=1
    echo "postgres ready (attempt $i)"
    break
  fi
  sleep 2
done
[ "$pg_ok" -eq 1 ] || { echo "ERROR: postgres not ready"; exit 1; }

echo
echo "=== [3] wait for Redis ==="
redis_ok=0
for i in $(seq 1 30); do
  if [ "$($COMPOSE exec -T redis redis-cli ping 2>/dev/null | tr -d '[:space:]')" = "PONG" ]; then
    redis_ok=1
    echo "redis ready (attempt $i)"
    break
  fi
  sleep 2
done
[ "$redis_ok" -eq 1 ] || { echo "ERROR: redis not ready"; exit 1; }

echo
echo "=== [4] apply PostgreSQL migrations ==="
for migration in migrations/*.sql; do
  echo "-- applying $migration"
  $COMPOSE exec -T postgres psql -U postgres -d aiagents -v ON_ERROR_STOP=1 < "$migration"
done
echo "migrations applied successfully"

echo
echo "=== [5] initialize Redis Streams ==="
bash scripts/init_redis_streams.sh

echo
echo "=== [6] PostgreSQL table list ==="
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c '\dt'

echo
echo "=== [7] Redis stream / consumer-group check ==="
streams=$($COMPOSE exec -T redis redis-cli --scan --pattern 'stream.*' </dev/null 2>/dev/null | sort)
for s in $streams; do
  grp=$($COMPOSE exec -T redis redis-cli XINFO GROUPS "$s" </dev/null 2>/dev/null | grep -cF 'name' || true)
  echo "  $s  ->  $grp consumer group(s)"
done

echo
echo "### init_local_runtime end: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "INIT_LOCAL_RUNTIME_DONE"
