#!/usr/bin/env bash
# Verify the Tempo trace backend: container ready, OTLP ports listening,
# Grafana datasource provisioned. Local/test only — contacts no cloud SaaS.
# Run from the repository root.
set -uo pipefail

COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_tracing_backend: $(date '+%Y-%m-%d %H:%M:%S %Z')"

echo
echo "=== tempo container state ==="
$COMPOSE ps tempo

echo
echo "=== tempo /ready ==="
ready=$(curl -sS -m 10 http://localhost:3200/ready || echo '')
echo "$ready"
if [ "$ready" = "ready" ] || echo "$ready" | grep -qi ready; then
  echo "TEMPO_READY: PASS"
else
  echo "TEMPO_READY: FAIL"
fi

echo
echo "=== tempo /status/version ==="
curl -sS -m 5 http://localhost:3200/status/version || echo "(unavailable)"
echo

echo
echo "=== OTLP ports listening (host) ==="
for entry in "OTLP gRPC:4317" "OTLP HTTP:4318" "Tempo HTTP:3200"; do
  label="${entry%%:*}"
  port="${entry##*:}"
  if (echo > /dev/tcp/127.0.0.1/$port) >/dev/null 2>&1; then
    echo "  ${label} (:${port})  ->  LISTENING"
  else
    echo "  ${label} (:${port})  ->  CLOSED"
  fi
done

echo
echo "=== OTLP HTTP endpoint smoke (POST /v1/traces with empty body) ==="
http_status=$(curl -sS -o /dev/null -w '%{http_code}' -m 5 \
  -X POST http://localhost:4318/v1/traces \
  -H 'Content-Type: application/x-protobuf' \
  --data-binary '' || echo 000)
echo "  HTTP $http_status"
if [ "$http_status" = "200" ] || [ "$http_status" = "400" ] || [ "$http_status" = "415" ]; then
  echo "OTLP_HTTP_ENDPOINT: PASS"
else
  echo "OTLP_HTTP_ENDPOINT: CHECK"
fi

echo
echo "=== grafana Tempo datasource (anonymous) ==="
ds=$(curl -sS -m 10 http://localhost:3000/api/datasources || echo '[]')
echo "$ds" | head -c 1500
echo
if echo "$ds" | grep -q '"type":"tempo"' && echo "$ds" | grep -q '"url":"http://tempo:3200"'; then
  echo "GRAFANA_TEMPO_DATASOURCE: PASS"
else
  echo "GRAFANA_TEMPO_DATASOURCE: CHECK"
fi

echo
echo "=== orchestrator OTEL env vars ==="
$COMPOSE exec -T orchestrator sh -c 'env | grep ^OTEL_' || echo "(orchestrator unavailable)"

echo
echo "VERIFY_TRACING_BACKEND_DONE"
