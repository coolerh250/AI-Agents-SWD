# AI Agents SWD — Manual Verification Guide

Copy-paste manual verification for a human operator on the `10.0.1.31`
test server. **Local/test only — no production action.**

> Safety contract: nothing below contacts a real cloud / GitHub / Slack
> / Kubernetes / LLM API, sends a real alert, or modifies a production
> resource. Alertmanager stays on the null receiver; the platform never
> sets `production_executed = true`.

---

## 0. Prerequisites

* SSH access to the test server (profile `aiagent-swd`,
  static IP `10.0.1.31`).
* Repository checked out at `/home/itadmin/AI-Agents-SWD`.
* Docker engine + Compose v2 installed.
* No real secrets in the environment — Vault runs in dev mode.

---

## 1. Connect & sync

```
ssh aiagent-swd
cd /home/itadmin/AI-Agents-SWD
git pull --ff-only
git log -1 --oneline
```

The latest commit hash should match what was just pushed to `main`.

---

## 2. Bring runtime up

```
docker compose -f infra/docker-compose/docker-compose.yml ps
docker compose -f infra/docker-compose/docker-compose.yml build
docker compose -f infra/docker-compose/docker-compose.yml up -d
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate prometheus grafana alertmanager tempo
```

Wait ~20 seconds for healthchecks to settle, then re-run
`docker compose ... ps` and confirm every service is `running (healthy)`.

---

## 3. Run the test suite

```
source .venv/bin/activate
pip install -r requirements.txt
./scripts/run_tests.sh
```

Expected: `pytest` all green; `ruff`, `black --check`, and `mypy` clean.

---

## 4. Run the runtime smoke battery

```
./scripts/check_runtime_state.sh
```

Expected: every `*_SMOKE` line ends in `PASS` and the script prints
`CHECK_RUNTIME_STATE_DONE`.

---

## 5. Verify tracing backend

```
./scripts/verify_tracing_backend.sh
```

Expected: `TEMPO_READY: PASS`, `OTLP_HTTP_ENDPOINT: PASS`,
`GRAFANA_TEMPO_DATASOURCE: PASS`, `VERIFY_TRACING_BACKEND_DONE`.

---

## 6. Verify end-to-end trace flow

```
./scripts/verify_trace_flow.sh
```

Expected: `TRACE_FLOW_SMOKE: PASS (trace_id=... covers all 7 services)`
and `VERIFY_TRACE_FLOW_DONE`.

---

## 7. Verify alerting

```
./scripts/verify_alerting.sh
```

Expected: `ALERTMANAGER_HEALTHY: PASS`,
`PROMETHEUS_RULES_LOADED: PASS`, `PROMETHEUS_RULES_NAMES: PASS`,
`ALERTMANAGER_OFFHOST_RECEIVER: PASS (null receiver only)`,
`VERIFY_ALERTING_DONE`.

---

## 8. Verify incident flow

```
./scripts/verify_incident_flow.sh
```

Expected: `INCIDENT_FLOW_SMOKE: PASS` and `VERIFY_INCIDENT_FLOW_DONE`.

---

## 9. Run the full platform observability verification

```
./scripts/verify_platform_observability.sh
```

Expected last lines:

```
CHECK_RUNTIME_STATE: PASS
VERIFY_TRACING_BACKEND: PASS
VERIFY_TRACE_FLOW: PASS
VERIFY_ALERTING: PASS
VERIFY_INCIDENT_FLOW: PASS
PLATFORM_OBSERVABILITY_VERIFY: PASS
VERIFY_PLATFORM_OBSERVABILITY_DONE
```

---

## 10. Spot-check health endpoints

```
for p in 8000 8001 8002 8003 8004 8010 8011 8012 8013 8014 8015; do
  printf "  :%s -> %s\n" "$p" "$(curl -sS -o /dev/null -w '%{http_code}' -m 5 http://localhost:$p/health)"
done
```

Every line should print `200`.

---

## 11. Build a workflow and watch it complete

```
ts=$(date +%s)
task_id="manual-verify-$ts"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$task_id\",\"request\":{\"type\":\"dev.test\",\"description\":\"manual verify\"}}"

# Watch progress until completed
for i in $(seq 1 20); do
  curl -sS "http://localhost:8000/workflow/progress/$task_id" \
    | python3 -m json.tool | head -n 30
  sleep 2
done
```

The final progress payload must show `"current_stage":"completed"` and
a non-empty `completed_agents` array containing all five agents.

---

## 12. Inspect the workflow timeline

```
curl -sS "http://localhost:8000/workflow/timeline/$task_id" \
  | python3 -m json.tool | head -n 60
```

Expected keys: `agent_timeline`, `traces`, `workflow_id`, `task_id`.

---

## 13. Open Grafana

* URL: `http://10.0.1.31:3000`
* Dashboards → `AI Agents SWD Platform`.
* Confirm: workflow / agent / retry panels populated, Active alerts
  (firing) stat panel visible, Service health (up per job) table
  visible, Active alerts over time timeseries visible.

---

## 14. Inspect Prometheus

```
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | head -n 40
curl -s http://localhost:9090/api/v1/rules   | python3 -m json.tool | head -n 60
curl -s http://localhost:9090/api/v1/alerts  | python3 -m json.tool | head -n 40
```

Every target must be `"health":"up"` and at least four `aiagents.*`
rule groups must be loaded.

---

## 15. Query Tempo for the manual trace

```
trace_id=$(curl -s "http://localhost:8000/workflow/progress/$task_id" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('trace_id',''))")
echo "trace_id=$trace_id"
sleep 6
curl -s "http://localhost:3200/api/traces/$trace_id" | head -c 1500
```

The response must include `service.name` entries for the seven services
(`communication-gateway`, `orchestrator`, `intake-agent`,
`requirement-agent`, `development-agent`, `qa-agent`, `devops-agent`).

---

## 16. Drive an incident

```
fail_task="manual-incident-$(date +%s)"
curl -sS -m 30 -X POST http://localhost:8004/intake/mock \
  -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$fail_task\",\"request\":{\"type\":\"dev.test\",\"simulate_failure\":true}}"

# Poll until the incident exists
for i in $(seq 1 30); do
  curl -sS "http://localhost:8000/incidents?task_id=$fail_task" \
    | python3 -m json.tool | head -n 25
  sleep 2
done
```

Then:

```
inc_id=$(curl -sS "http://localhost:8000/incidents?task_id=$fail_task" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['incidents'][0]['incident_id'])")
echo "inc_id=$inc_id"
curl -sS -X POST "http://localhost:8000/incidents/$inc_id/ack"     | python3 -m json.tool
curl -sS -X POST "http://localhost:8000/incidents/$inc_id/resolve" | python3 -m json.tool
```

And confirm the workflow flipped to `failed`:

```
curl -sS "http://localhost:8000/workflow/$fail_task" \
  | python3 -m json.tool | grep -E '"stage"|"status"|"production_executed"'
```

`stage` must be `failed`, `status` must be `failed`, and
`production_executed` must be `false`.

---

## 17. Confirm `production_executed = false` across all deployments

```
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COUNT(*) FROM deployment_records
    WHERE metadata->>'production_executed'='true' OR environment='production';"
```

Expected output: `0`.

---

## 17n. Verify the controlled notification delivery (Stage 22)

```
./scripts/verify_notification_delivery.sh
```

The script drives one Discord sandbox dev.test task, waits for the
workflow to complete, then asserts the unified delivery /
operations / audit path. It ends with
`NOTIFICATION_DELIVERY_VERIFY: PASS`.

Manual smoke:

```
curl http://localhost:8008/health
curl http://localhost:8008/status | python3 -m json.tool
curl http://localhost:8008/metrics | grep ^notification_worker_

# Inspect deliveries for a task
curl -sS "http://localhost:8007/discord/deliveries/$task" | python3 -m json.tool

# Inspect the unified operations view (Stage 20 endpoint now carries
# the notification_deliveries section)
curl -sS "http://localhost:8000/operations/workflows/$task" | python3 -m json.tool \
  | grep -A8 notification_deliveries

# Confirm the controlled real-Discord guard
curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  http://localhost:8008/discord/real/test-message \
  -H 'Content-Type: application/json' \
  -d '{"content":"sandbox real Discord guard verification"}'
# expected: 409 (unless DISCORD_BOT_TOKEN + DISCORD_TEST_CHANNEL_ID +
# RUN_REAL_DISCORD_TEST=true are deliberately loaded into the
# notification-worker container)

# Production safety must remain at 0
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records
    WHERE metadata->>'production_executed'='true' OR environment='production';"
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states
    WHERE execution_result->>'production_executed'='true';"
```

The controlled real-Discord test is **opt-in only** and is **not**
part of any default verify run. Operator recipe (sets the env in the
shell; never commits it):

```
export DISCORD_BOT_TOKEN
export DISCORD_TEST_CHANNEL_ID
export RUN_REAL_DISCORD_TEST=true
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate notification-worker
curl -sS -X POST http://localhost:8008/discord/real/test-message \
  -H 'Content-Type: application/json' \
  -d '{"content":"manual controlled live test"}'
```

The response includes the Discord `message_id` — never the bot
credential.

---

## 17d. Verify the Discord Gateway sandbox (Stage 21)

The Discord Gateway is sandbox by default. Run:

```
./scripts/verify_discord_gateway.sh
```

The script drives one dev.test sandbox message and one
production.deploy sandbox message, asserts the unified audit /
notification / operations path picks up the Discord origin, and
confirms that `/discord/real/test-message` is refused without the
opt-in env vars. It ends with
`DISCORD_GATEWAY_VERIFY: PASS`.

Manual smoke:

```
curl http://localhost:8007/health
curl http://localhost:8007/status | python3 -m json.tool
curl http://localhost:8007/metrics | grep ^discord_

# Create a dev.test sandbox task
curl -sS -X POST http://localhost:8007/discord/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"/ai task type=dev.test description=\"manual discord sandbox verification\"","channel_id":"sandbox","user_id":"operator"}' \
  | python3 -m json.tool

# Follow the task
curl -sS "http://localhost:8007/discord/tasks/$task" | python3 -m json.tool

# Audit / notification confirmation
curl -sS "http://localhost:8003/audit/events?decision_type=discord_intake&limit=5" | python3 -m json.tool
curl -sS "http://localhost:8004/notifications?count=200" | python3 -m json.tool | grep discord.task

# Real-Discord opt-in MUST be refused
curl -sS -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8007/discord/real/test-message \
  -H 'Content-Type: application/json' \
  -d '{"channel_id":"sandbox","message":"should-not-go"}'
# expected: 409
```

The optional real Discord test is **not** part of the default
verify run; it is opt-in only and must NEVER print the bot credential:

```
export DISCORD_BOT_TOKEN  # set in your shell; never commit it
export RUN_REAL_DISCORD_TEST=true
curl -sS -X POST http://localhost:8007/discord/real/test-message \
  -H 'Content-Type: application/json' \
  -d '{"channel_id":"<discord-test-channel-id>","message":"manual sandbox smoke"}'
```

The response carries the Discord `message_id` only — never the bot
credential.

---

## 17ops. Verify the Operations Control API (Stage 20)

The orchestrator hosts a unified read-only operator namespace
(`/operations/*`).

```
./scripts/verify_operations_view.sh
```

The script drives one normal workflow + one github-pipeline
dry-run workflow, waits for both to complete, then exercises every
`/operations/*` endpoint and ends with
`OPERATIONS_VIEW_VERIFY: PASS`.

Inspect the endpoints individually:

```
curl -sS http://localhost:8000/operations/health
curl -sS http://localhost:8000/operations/summary    | python3 -m json.tool
curl -sS http://localhost:8000/operations/agents     | python3 -m json.tool
curl -sS http://localhost:8000/operations/streams    | python3 -m json.tool
curl -sS http://localhost:8000/operations/safety     | python3 -m json.tool
curl -sS "http://localhost:8000/operations/incidents?limit=5" | python3 -m json.tool
curl -sS "http://localhost:8000/operations/dlq?limit=5"       | python3 -m json.tool
curl -sS "http://localhost:8000/operations/workflows/$task"   | python3 -m json.tool
curl -sS "http://localhost:8000/operations/github/$task"      | python3 -m json.tool
```

`/operations/safety` must show every production counter at `0`
and `result` either `safe` or `warning` (warnings cover external
Alertmanager receivers and `GITHUB_TOKEN` + `dry_run=false`). The
local/test stack has none of those configured, so `safe` is the
expected outcome.

`/operations/workflows/$task` is the single most useful
operator endpoint — every other status surface (`/workflow/*`,
`/executions`, `/audit/events/{task_id}`, `/incidents`,
`/notifications`, `gh pr view`) is reachable from its sections.

---

## 17a. Verify the unified audit path (Stage 19)

The audit-worker consumes `stream.audit` and writes `audit_logs`:

```
curl -sS http://localhost:8006/health
curl -sS http://localhost:8006/status | python3 -m json.tool
curl -sS http://localhost:8006/metrics | grep audit_worker_
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T redis redis-cli XINFO GROUPS stream.audit
./scripts/verify_unified_audit.sh
```

`/health` returns `{"service":"audit-worker","status":"ok"}`.
`/status` shows `"running":true`, `"group":"audit-group"`, and the
processed counter incrementing as workflows run. `XINFO GROUPS` lists
`audit-group` with `consumers >= 1`. `verify_unified_audit.sh` ends
with `UNIFIED_AUDIT_VERIFY: PASS`.

Query the unified audit DB directly:

```
curl -sS "http://localhost:8003/audit/events?limit=5" | python3 -m json.tool
curl -sS "http://localhost:8003/audit/events?agent=qa-agent&limit=5" \
  | python3 -m json.tool
curl -sS "http://localhost:8003/audit/events?decision_type=github_pr_integration&limit=5" \
  | python3 -m json.tool
```

A pipeline-triggered workflow with `github.enabled=true` produces
`github_pr_integration` (devops-agent) and `github_automation`
(github-automation) rows in `audit_logs`.

`/workflow/timeline/{task_id}` carries `audit_timeline` next to
`agent_timeline` / `retry_timeline`:

```
curl -sS "http://localhost:8000/workflow/timeline/$task" \
  | python3 -m json.tool | grep -A2 audit_timeline | head -30
```

---

## 17b. Controlled real GitHub validation (Stage 23)

Stage 23 ships `verify_real_github_validation.sh` and a dedicated
endpoint, `POST /github/workflow/real-test-pr`. The cluster runs in
sandbox-only mode by default — the endpoint refuses every real-test
request with HTTP 409 and writes one
`audit_logs.decision_type=github_real_test_blocked` row per refusal.

```
./scripts/verify_real_github_validation.sh
```

### Expected SKIPPED mode result

When `GITHUB_TOKEN`, `RUN_REAL_GITHUB_TEST`, and `GITHUB_TEST_REPO` are
unset (the platform default), the script must end with:

```
REAL_GITHUB_TEST_SKIPPED: PASS
checks passed: 12 / 12
REAL_GITHUB_VALIDATION_VERIFY: PASS
```

The script also asserts:

* `/health` carries `real_github_test_enabled=false` and
  `test_repo_configured=false`;
* `/operations/safety` carries the four boolean fields
  `github_has_token`, `real_github_test_enabled`,
  `github_test_repo_configured`, and `github_external_write_enabled`,
  all set to `false`;
* `/github/workflow/real-test-pr` returns HTTP 409 with a
  `safety_guard_result` body that has no token-shaped substring;
* `audit_logs.decision_type=github_real_test_blocked` appears for the
  refused task_id;
* `/operations/github/{task_id}.real_test.safety_guard_result.latest_blocked`
  carries the same reason;
* `/github/workflow/demo-pr` dry-run flow still works (regression);
* `deployment_records.production_executed=true` and
  `workflow_states.production_executed=true` counts are both `0`.

### Optional real GitHub test procedure

The optional path is opt-in only. Run it from a shell where the
operator has explicitly exported the three env vars:

```
export GITHUB_TOKEN   # set in the shell only, never committed
export RUN_REAL_GITHUB_TEST=true
export GITHUB_TEST_REPO=coolerh250/AI-Agents-SWD

cd /home/itadmin/AI-Agents-SWD
docker compose -f infra/docker-compose/docker-compose.yml up -d \
  --force-recreate github-automation orchestrator
./scripts/verify_real_github_validation.sh
```

Expected, when the run succeeds:

```
REAL_GITHUB_TEST_EXECUTED: PASS
REAL_GITHUB_TEST_AUDIT: PASS
REAL_GITHUB_TEST_NOTIFICATION: PASS
REAL_GITHUB_TEST_OPERATIONS_VIEW: PASS
REAL_GITHUB_TEST_PR_URL=https://github.com/coolerh250/AI-Agents-SWD/pull/<n>
REAL_GITHUB_VALIDATION_VERIFY: PASS
```

After verifying:

1. Close the PR on GitHub (do **not** merge).
2. Delete the head branch `ai-agents-test/<task_id>` on GitHub.
3. Revoke the PAT and unset `RUN_REAL_GITHUB_TEST`.
4. Restart `github-automation` so the env returns to sandbox-only.

### Safety SQL `production_executed=false` query

Whether or not the real test ran, the production safety counters must
remain `0`:

```
docker exec aiagents-test-postgres-1 psql -U postgres -d aiagents -c "
select count(*) as deployment_prod_true
from deployment_records
where metadata->>'production_executed'='true'
or environment='production';
"

docker exec aiagents-test-postgres-1 psql -U postgres -d aiagents -c "
select count(*) as workflow_prod_true
from workflow_states
where execution_result->>'production_executed'='true';
"
```

The Stage 23 controlled-real flow targets a sandbox repo only — it
never writes to `deployment_records` and never sets
`workflow_states.execution_result.production_executed=true`.

---

## 17c. Staging runtime hardening (Stage 24)

Stage 24 ships an aggregate verifier and four standalone scripts. The
local cluster on `10.0.1.31` keeps its existing trust-auth /
Vault-dev-mode / null-receiver posture; Stage 24 only adds the tools
an operator would use to promote the platform to staging.

```
./scripts/verify_staging_hardening.sh
```

Expected (default local cluster):

```
RUNTIME_CONFIG_VALIDATION: PASS
PRODUCTION_SAFETY_GATE: PASS
BACKUP_RESTORE_VERIFY: PASS
RUNTIME_HEALTH_SNAPSHOT_DONE: PASS
HEALTH_LOG_NO_TOKEN: PASS
STAGING_TEMPLATE_NO_TRUST_AUTH: PASS
ENV_EXAMPLES_PLACEHOLDER_ONLY: PASS
PRODUCTION_EXECUTED_FALSE: PASS
SECRET_REDACTION: PASS
checks passed: 9 / 9
STAGING_HARDENING_VERIFY: PASS
```

### Standalone scripts

* `./scripts/validate_runtime_config.sh --mode local` — must end
  `RUNTIME_CONFIG_VALIDATION: PASS`.
* `./scripts/production_safety_gate.sh` — must end
  `PRODUCTION_SAFETY_GATE: PASS`. Inspects `deployment_records`,
  `workflow_states`, `/operations/safety`, Alertmanager receivers.
* `./scripts/runtime_health_snapshot.sh` — writes
  `source/runtime-health.log`. The file must contain no token-shaped
  substring; `verify_staging_hardening.sh` greps for token-prefix
  patterns (the GitHub PAT prefixes and the HTTP auth-header prefixes
  used by GitHub / Discord) as a regression guard.
* `./scripts/verify_backup_restore.sh` — takes a fresh `pg_dump`,
  asserts `pg_restore -l` parses the TOC, confirms the live DB's
  table count is untouched, and asserts the restore guard refuses
  without `ALLOW_RESTORE=true`. Cleans up the temporary file.

### Backup / restore smoke

`backups/` is gitignored. The verify script's expected output:

```
backup_file=backups/aiagents-<ts>.dump
tables_before=<N>
pg_restore_toc_lines=<>=5
tables_after=<same as before>
restore_refusal: RESTORE_POSTGRES: FAIL (ALLOW_RESTORE!=true ...)
BACKUP_RESTORE_VERIFY: PASS
```

If you ever need to restore (do **not** run this against the test
cluster casually):

```
ALLOW_RESTORE=true ./scripts/restore_postgres.sh backups/aiagents-<ts>.dump
```

The restore script refuses outright when `APP_ENV` is `production` or
`production-check`.

### Sign-off checklist additions

The Stage 24 items below are appended to the Section 18 sign-off list:

* [ ] `./scripts/verify_staging_hardening.sh` ended
      `STAGING_HARDENING_VERIFY: PASS`.
* [ ] `./scripts/validate_runtime_config.sh --mode local` ended
      `RUNTIME_CONFIG_VALIDATION: PASS`.
* [ ] `./scripts/production_safety_gate.sh` ended
      `PRODUCTION_SAFETY_GATE: PASS` with every production counter at `0`.
* [ ] `./scripts/runtime_health_snapshot.sh` produced
      `source/runtime-health.log`; the file is at most a few KB and
      contains no token-shaped substring.
* [ ] `backups/aiagents-<ts>.dump` exists locally on the host (was
      created by `verify_backup_restore.sh`) but was NOT committed to
      the repo.

---

## 18. Sign-off checklist

* [ ] `git log -1` matches the commit the team agreed to ship.
* [ ] All 19 services + audit-worker reported `running (healthy)`.
* [ ] `./scripts/run_tests.sh` ended green.
* [ ] `./scripts/verify_unified_audit.sh` ended `UNIFIED_AUDIT_VERIFY: PASS`.
* [ ] `./scripts/verify_operations_view.sh` ended `OPERATIONS_VIEW_VERIFY: PASS`.
* [ ] `./scripts/verify_discord_gateway.sh` ended `DISCORD_GATEWAY_VERIFY: PASS`.
* [ ] `./scripts/verify_notification_delivery.sh` ended `NOTIFICATION_DELIVERY_VERIFY: PASS`.
* [ ] `curl http://localhost:8008/health` shows `mode=sandbox` and
      the `has_discord_token` flag is `false` (unless an opt-in
      controlled-real run was deliberately set up).
* [ ] `POST /discord/real/test-message` on `notification-worker`
      returns HTTP 409 unless `DISCORD_BOT_TOKEN`,
      `DISCORD_TEST_CHANNEL_ID`, and `RUN_REAL_DISCORD_TEST=true` are
      all set.
* [ ] `curl http://localhost:8007/health` shows
      `mode=sandbox` and the `has_token` flag is `false` (unless
      an opt-in real Discord test was deliberately enabled).
* [ ] `POST /discord/real/test-message` returns HTTP 409 unless
      `DISCORD_BOT_TOKEN` and `RUN_REAL_DISCORD_TEST=true` are
      both set.
* [ ] `curl http://localhost:8000/operations/safety` shows
      `result=safe` (or `warning` for documented non-fatal items) and
      every production counter at `0`.
* [ ] `./scripts/verify_real_github_validation.sh` ended
      `REAL_GITHUB_VALIDATION_VERIFY: PASS` and reported
      `REAL_GITHUB_TEST_SKIPPED: PASS` (unless the operator
      deliberately opted in to a controlled-real run, in which case
      `REAL_GITHUB_TEST_EXECUTED: PASS` is present and the PR has
      been closed + the branch deleted after verification).
* [ ] `curl http://localhost:8005/health` shows
      `real_github_test_enabled=false` and `test_repo_configured=false`
      (unless an opt-in controlled-real run was deliberately set up).
* [ ] `POST /github/workflow/real-test-pr` returns HTTP 409 unless
      `GITHUB_TOKEN`, `RUN_REAL_GITHUB_TEST=true`, and
      `GITHUB_TEST_REPO` are all set.
* [ ] `./scripts/verify_platform_observability.sh` ended
      `PLATFORM_OBSERVABILITY_VERIFY: PASS`.
* [ ] Manual workflow reached `completed`, trace covered all 7
      services, incident lifecycle (create → ack → resolve) worked.
* [ ] `deployment_records` shows zero rows with
      `production_executed = true` or `environment = production`.
* [ ] `workflow_states.execution_result->>'production_executed'='true'`
      count is `0`.
* [ ] Alertmanager `/api/v2/receivers` mentions no external
      Slack / Discord / Telegram / PagerDuty / webhook / email
      receiver.

If every box is ticked, the platform is ready for the next iteration.
Nothing on this checklist authorizes a production deploy.
