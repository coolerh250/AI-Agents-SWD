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

## 17d. Staging environment bring-up (Stage 25)

Stage 25 actually brings up a sibling cluster on `aiagents-staging`
under host ports offset by +10000. The local/test stack stays
untouched. Default `verify_staging_runtime.sh` tears the staging
stack down after the assertions; pass `--keep-running` to leave it
up for manual inspection.

```
./scripts/verify_staging_runtime.sh
```

Expected (default mode):

```
STAGING_ENV_PRESENT: PASS
STAGING_VALIDATOR: PASS
STAGING_VAULT_DEV_MODE_ALLOWED: WARN (documented escape hatch)
STAGING_START: PASS
STAGING_HEALTH: PASS
STAGING_POSTGRES_PASSWORD_AUTH: PASS
STAGING_MIGRATIONS_APPLIED: PASS
STAGING_E2E_WORKFLOW: PASS
STAGING_GITHUB_DRY_RUN: PASS
STAGING_AUDIT_TIMELINE: PASS
STAGING_NOTIFICATION_DELIVERY: PASS
STAGING_OPERATIONS_SAFETY: PASS
STAGING_PRODUCTION_SAFETY: PASS
LOCAL_TEST_UNAFFECTED: PASS
STAGING_STOP: PASS
checks passed: 12 / 12
STAGING_RUNTIME_VERIFY: PASS
```

### Standalone staging commands

* `./scripts/generate_staging_env.sh` — produces
  `infra/runtime/.env.staging.local` (gitignored, chmod 600). Refuses
  to overwrite without `ALLOW_OVERWRITE=true`.
* `./scripts/start_staging_runtime.sh [--rebuild]` — validates +
  brings staging up + applies migrations + initialises Redis Streams.
* `./scripts/stop_staging_runtime.sh [--volumes]` — tears staging
  down; `--volumes` purges the staging data volumes too.
* `./scripts/check_staging_runtime.sh` — read-only health summary on
  +10000 host ports.
* `./scripts/verify_staging_backup_restore.sh` — fresh `pg_dump`
  against staging Postgres, asserts the local/test DB is untouched.
* `./scripts/runtime_health_snapshot.sh --env staging` — writes
  `source/runtime-health-staging.log`.

### Local/test regression after staging bring-up

After staging has been brought up and torn down, re-run the standard
local/test suite to confirm no regression:

```
./scripts/check_runtime_state.sh
./scripts/verify_discord_gateway.sh
./scripts/verify_notification_delivery.sh
./scripts/verify_operations_view.sh
./scripts/verify_unified_audit.sh
./scripts/verify_github_pipeline_flow.sh
./scripts/verify_real_github_validation.sh
./scripts/verify_platform_observability.sh
```

All must remain green.

### Staging production safety SQL

If the staging stack is left running (`--keep-running`), query the
staging Postgres directly:

```
docker compose -p aiagents-staging \
  -f infra/docker-compose/docker-compose.staging.yml \
  --env-file infra/runtime/.env.staging.local \
  exec postgres psql -U aiagents_app -d aiagents -c "
select count(*) as deployment_prod_true
from deployment_records
where metadata->>'production_executed'='true'
or environment='production';
"
```

Both counts must be `0` on staging too. If the verify script tore
the staging stack down (default), the query simply isn't applicable
until the next `start_staging_runtime.sh`.

### Stage 25 sign-off checklist additions

* [ ] `./scripts/verify_staging_runtime.sh` ended
      `STAGING_RUNTIME_VERIFY: PASS` (12 / 12) with the staging
      stack torn down (or, when run with `--keep-running`, the
      staging stack is healthy and `production_executed=0`).
* [ ] `./scripts/verify_staging_backup_restore.sh` ended
      `STAGING_BACKUP_RESTORE_VERIFY: PASS`; the local/test DB's
      table count was sampled identical before + after.
* [ ] `./scripts/runtime_health_snapshot.sh --env staging` produced
      `source/runtime-health-staging.log` with no token-shaped
      substring.
* [ ] `infra/runtime/.env.staging.local` exists on the host with
      `chmod 600` permissions and was NOT committed to the repo.
* [ ] After staging tear-down, every previous local/test verify
      script (`verify_discord_gateway.sh`,
      `verify_notification_delivery.sh`,
      `verify_operations_view.sh`,
      `verify_unified_audit.sh`,
      `verify_github_pipeline_flow.sh`,
      `verify_real_github_validation.sh`,
      `verify_platform_observability.sh`) still PASS.

---

## 17e. External secrets baseline (Stage 26)

```
./scripts/list_required_secrets.py
./scripts/bootstrap_mock_vault_secrets.sh
SECRET_PROVIDER=mock-vault ./scripts/validate_runtime_config.sh \
  --mode staging --env-file infra/runtime/.env.staging.local
./scripts/verify_secret_rotation_smoke.sh
./scripts/scan_for_secret_leaks.sh
./scripts/verify_staging_secrets.sh
```

Expect every script to end `PASS`. Confirm:

* `infra/runtime/.mock-vault-secrets.local.json` exists with mode `600`
  and is **gitignored**.
* `validate_runtime_config.py --mode production-check` refuses both
  `SECRET_PROVIDER=mock-vault` and `SECRET_PROVIDER=env` — see
  [`secrets-management.md`](secrets-management.md).
* `GET http://localhost:18000/operations/safety` (during the staging
  bring-up) includes the four Stage 26 fields `secret_provider`,
  `vault_configured`, `mock_vault_enabled`, and the listing field
  `missing_required_secrets`. No value-shaped string appears anywhere
  in the response.
* `source/runtime-health.log` and `source/runtime-health-staging.log`
  carry no real-token prefix substring (the scanner sweeps them).

## 17f. Discord-driven flexible task execution loop (Stage 27)

```
./scripts/verify_flexible_task_execution_loop.sh
```

Expect `FLEXIBLE_TASK_EXECUTION_VERIFY: PASS` (20/20). The script
covers four scenarios:

* **simple_task** — short non-dev request stays `simple_task`, no
  Scrum fields.
* **delivery_task** — dev-shaped request reaches
  `ready_for_development`, agent pipeline completes, GitHub dry-run
  PR is created.
* **needs_clarification** — `"TBD"` description blocks the pipeline;
  answer + resume promotes the work item to
  `ready_for_development`.
* **scrum_project** — explicit Scrum vocabulary turns on
  `acceptance_criteria` / `definition_of_done` / `scrum_metadata`.
  `simple_task` work items must still carry `null` for those
  fields.

Confirm:

* `GET /operations/workflows/<task_id>` carries a
  `task_execution` section with `work_item`,
  `agent_discussions`, `clarification_requests`,
  `execution_plan`, `assumptions`, `open_questions`, `risks`,
  `ready_for_development` booleans — and `production_executed=false`
  throughout.
* `GET /operations/summary.task_execution_summary` carries
  `total_work_items`, `simple_task_count`, `delivery_task_count`,
  `scrum_project_count`, `needs_clarification_count`,
  `ready_for_development_count`, `blocked_count`.
* No `acceptance_criteria` / `definition_of_done` /
  `scrum_metadata` on `simple_task` / `delivery_task` work items.
* Discord-gateway `/discord/clarifications/<task_id>` and
  `/discord/clarifications/<id>/answer` work end-to-end without
  contacting the real Discord API.

## 17g. Controlled code generation workspace (Stage 28)

```
./scripts/verify_controlled_code_generation.sh
```

Expect `CONTROLLED_CODE_GENERATION_VERIFY: PASS` (18/18). The script
covers three scenarios:

* **docs generation** — description triggers the `documentation`
  template; `docs/generated/<task_id>.md` is recorded as a
  `code_change_artifact` with a non-empty diff and a `pr_draft`
  marked `status=ready`. devops-agent forwards the PR draft to
  `github-automation /github/workflow/demo-pr` (`dry_run=true`).
* **API generation** — description triggers the `demo_api` template;
  both `apps/demo-generated/<slug>_api.py` and
  `tests/generated/test_<slug>_api.py` are written, `py_compile`
  passes locally, `pr_draft.test_results.status=passed`.
* **policy block** — unclassifiable description flips the workspace
  to `blocked`, `generator_mode=blocked`, no PR draft is created,
  `code_generation_blocked` audit + `code.generation_blocked`
  notification are emitted.

Confirm:

* `GET /operations/workflows/<task_id>.code_generation` exposes
  `workspace`, `status`, `generator_mode`, `changed_files`,
  `code_change_artifacts`, `pr_draft`, `validation_result`,
  `risk_assessment`, `blocked_reason`, and `production_executed=false`
  throughout.
* `GET /operations/code/workspaces`, `…/workspaces/<task_id>`,
  `…/artifacts/<task_id>`, `…/pr-drafts/<task_id>` all respond
  read-only with no secret leakage.
* `GET /operations/summary.code_generation_summary` carries
  `total_workspaces`, `ready_for_pr_draft`, `blocked_count`,
  `deterministic_count`, `total_artifacts`, `validated_artifacts`,
  `total_pr_drafts`.
* `GET /discord/tasks/<task_id>` carries `code_generation_status`,
  `changed_files_count`, `pr_draft_status`, `validation_status`,
  `github_dry_run_pr_url`, `code_generation_blocked_reason`.
* `git status --short` after the run is empty — generated workspace
  files NEVER end up committed (the `.workspaces/` rule blocks them).
* `code_workspaces.generator_mode='deterministic_template'` for every
  successful row; `'blocked'` only for refused rows.
* No row in `pr_draft_artifacts.github_dry_run_result` has
  `dry_run=false` or `production_executed=true`.

## 17h. QA-guided validation + auto-fix loop (Stage 29)

```
./scripts/verify_qa_auto_fix_loop.sh
```

Expect `QA_AUTO_FIX_LOOP_VERIFY: PASS` (15/15). The script covers
three scenarios:

* **QA pass** — a clean delivery_task generates a workspace, the
  qa-agent passes (`final_result=pass`), the devops-agent's
  dry-run PR delivers, and the workflow reaches `completed`.
* **auto-fix loop** — the same API task exercises the
  loop machinery: `qa_validation_runs` rows recorded, the
  `/operations/qa/auto-fix/<task_id>` endpoint reachable, the
  development-agent's auto-fix consumer visible via the dev-agent
  `/status.autofix` block.
* **blocked** — an unclassifiable description flips the workspace
  to `blocked`; `qa_validation.qa_passed=false`; no
  `pr_draft_artifact` is created. The qa-agent never falsely
  passes a blocked workspace.

Confirm:

* `GET /operations/workflows/<task_id>.qa_validation` exposes
  `latest_run`, `status`, `final_result`, `findings`,
  `blocking_findings_count`, `auto_fix_requests`,
  `auto_fix_attempts`, `max_auto_fix_attempts`,
  `blocked_for_human_review`, `qa_passed`, and
  `production_executed=false`.
* `GET /operations/qa/runs`, `…/runs/<task_id>`,
  `…/findings/<task_id>`, `…/auto-fix/<task_id>` all respond
  read-only with no secret leakage.
* `GET /operations/summary.qa_summary` carries
  `total_validation_runs`, `passed_runs`, `failed_runs`,
  `blocked_for_human_review_count`, `auto_fix_requested_count`,
  `total_findings`.
* `GET /discord/tasks/<task_id>` carries `qa_status`,
  `qa_final_result`, `qa_findings_count`,
  `blocking_findings_count`, `auto_fix_attempts`,
  `blocked_for_human_review`.
* `git status --short` is empty after the run (workspaces are
  gitignored, the auto-fix doesn't change the working tree).
* `QA_MAX_AUTO_FIX_ATTEMPTS` honored — an env value of `1`
  forces a blocked outcome on the second pass.
* No `qa_findings` row with `severity in ('error','critical')`
  AND `status='open'` survives a `final_result=pass`.

## 17i. LLM-assisted development planning guardrails (Stage 30)

```
./scripts/verify_llm_guardrails.sh
./scripts/verify_llm_assisted_development.sh
```

Expect `LLM_GUARDRAILS_VERIFY: PASS` (5/5) and
`LLM_ASSISTED_DEVELOPMENT_VERIFY: PASS` (12/12). The default mode is
`LLM_PROVIDER=mock` with `ENABLE_LLM_ASSISTED_PLANNING=false` (the
deterministic Stage 28 generator handles the workflow untouched).
When LLM-assisted planning is opted in (`ENABLE_LLM_ASSISTED_PLANNING=true`),
the development-agent gates the deterministic generator on the
`LLMSafetyPolicy` result.

Confirm:

* `GET /operations/safety` exposes `llm_provider`, `llm_real_enabled`,
  `llm_external_call_enabled`, `llm_policy_enforced`,
  `llm_requires_human_review` — never the API key value.
* `GET /operations/workflows/<task_id>.llm_assistance` carries
  `enabled`, `provider`, `interactions`, `proposals`, `latest_proposal`,
  `latest_safety_result`, `requires_human_review`, `blocked`,
  `usage_summary`, `policy_violations`.
* `GET /operations/llm/interactions`, `…/interactions/<task_id>`,
  `…/proposals/<task_id>`, `…/usage` all respond read-only.
* `GET /operations/summary.llm_summary` carries
  `total_interactions`, `total_proposals`, `blocked_proposals`,
  `policy_passed_proposals`, `accepted_proposals`, `total_tokens`,
  `estimated_cost`.
* `GET /discord/tasks/<task_id>` carries `llm_provider`,
  `llm_proposal_status`, `llm_requires_human_review`,
  `llm_policy_blocked`, `llm_policy_violations_count`,
  `llm_usage_total_tokens`.
* Real LLM call: `REAL_LLM_TEST_SKIPPED: PASS` unless every gate
  (`RUN_REAL_LLM_TEST=true`, `ENABLE_REAL_LLM_NETWORK_CALL=true`, a
  provider key) is aligned — and even then, Stage 30 still refuses
  to dial the network.
* `git status --short` is empty after the run; no LLM-proposed file
  enters the working tree.
* No `llm_interactions` row carries a literal API key value; previews
  are redacted before persistence.

## 17j. Flexible human approval policy + LLM promotion (Stage 31)

```
./scripts/verify_flexible_human_approval_policy.sh
./scripts/verify_llm_proposal_promotion.sh
```

Expect `FLEXIBLE_HUMAN_APPROVAL_POLICY_VERIFY: PASS` (14/14) and
`LLM_PROPOSAL_PROMOTION_VERIFY: PASS` (4/4). Five scenarios are
covered:

* **per_action** — explicit approval required; orchestrator refuses
  to auto-promote.
* **per_feature** — a task-bound policy authorises promotions inside
  its allowlist; cross-task use refused.
* **per_stage** — a stage-bound policy authorises actions while the
  workflow is in that stage; other stages refused.
* **delegated** — fully-constrained delegated policy authorises
  actions while `actions_used < max_actions`, `files_changed ≤
  max_files_changed`, and `expires_at` has not passed.
* **hard safety block** — `production_deploy`, `real_github_write`,
  denylist-path mutation, secret content, destructive command are
  ALWAYS refused regardless of any policy authorising them.

Confirm:

* `GET /operations/workflows/{task_id}.approval_policy` carries
  `active_policies`, `approval_mode`, `decisions`,
  `delegated_actions_used`, `delegated_actions_remaining`,
  `revoked_policies`, `expired_policies`, `hard_policy_blocks`,
  `promotions`.
* `GET /operations/approval-policies`,
  `…/approval-policies/{task_id}`, `…/approval-decisions/{task_id}`
  respond read-only.
* `GET /operations/summary.approval_policy_summary` carries
  `total_policies`, `active_policies`, `delegated_policies`,
  `per_feature_policies`, `per_stage_policies`, `revoked_policies`,
  `total_decisions`, `approved_decisions`, `rejected_decisions`,
  `total_promotions`, `promoted_count`, `blocked_by_policy_count`.
* `GET /operations/safety` carries `delegated_agent_enabled`,
  `active_delegated_policies`, `hard_policy_enforced=true`,
  `production_delegation_allowed=false`,
  `real_github_delegation_allowed=false`.
* `GET /discord/tasks/{task_id}` carries `approval_mode`,
  `active_approval_policy`, `delegated_actions_used`,
  `delegated_actions_remaining`, `latest_approval_decision`,
  `llm_promotion_status`.
* `POST /llm/proposals/<unknown>/promote` returns `404`.
* `POST /approval-policies` with `approval_mode=delegated` but
  missing constraints returns `400 delegated_missing:<field>`.
* `git status --short` is empty after the run; promotions do not
  touch the working tree.

## 17k. Real integration sandbox pilot (Stage 32)

The pilot is opt-in. The default test cluster never has the env vars
set, so every real-mode verification runs in SKIPPED mode and the
master verify script still ends `REAL_INTEGRATION_PILOT_VERIFY: PASS`.

```bash
./scripts/check_real_integration_inputs.sh
./scripts/verify_real_discord_pilot.sh
./scripts/verify_real_github_sandbox_pilot.sh
./scripts/verify_real_integration_pilot.sh
```

Expected (skipped mode):

* `REAL_INTEGRATION_INPUTS: SKIPPED` (no env vars set is the
  intended default; the script also handles BLOCKED for partial env).
* `REAL_DISCORD_TEST_REFUSED_DEFAULT: PASS` + `REAL_DISCORD_TEST_SKIPPED: PASS`.
* `REAL_GITHUB_SANDBOX_REFUSED_DEFAULT: PASS` + `REAL_GITHUB_SANDBOX_TEST_SKIPPED: PASS`.
* `OPERATIONS_REAL_INTEGRATIONS: PASS`.
* `production_safety` counters both zero.
* `REAL_INTEGRATION_PILOT_VERIFY: PASS`.

Operations surfaces:

* `GET /operations/real-integrations` returns the inputs snapshot +
  Discord/GitHub counters + warnings (degrades silently to zeros if
  the audit / notification store is unreachable).
* `GET /operations/safety` carries `real_discord_inputs_present`,
  `real_discord_test_enabled`, `real_discord_guard_active`,
  `real_github_inputs_present`, `github_sandbox_guard_active`,
  `real_llm_enabled`, `production_deploy_enabled`.

The operator runbook lives at
[`docs/operations/real-integration-pilot.md`](./real-integration-pilot.md).

## 17l. Real Discord delivery filter (Stage 33)

Stage 33 fixed the Step 31R "autospam" blocker: even with real Discord
env live, the `notification-worker` stream consumer now defaults to
blocking every internal event (`workflow.*`, `qa.*`, `code.*`,
`github.*`, …) and only promotes explicit allowlist entries to a real
Discord call.

```bash
./scripts/verify_real_discord_delivery_filter.sh
./scripts/check_runtime_state.sh | grep -E 'REAL_DISCORD_(DELIVERY|AUTOSPAM|ALLOWED|DENYLIST|POLICY)'
```

Expected (sandbox / default cluster):

* `REAL_DISCORD_DELIVERY_POLICY_SMOKE: PASS`
* `REAL_DISCORD_AUTOSPAM_BLOCK_SMOKE: PASS (sandbox; policy default-deny)`
* `REAL_DISCORD_ALLOWED_EVENT_SMOKE: PASS`
* `REAL_DISCORD_DENYLIST_SMOKE: PASS`
* `REAL_DISCORD_POLICY_OPERATIONS_SMOKE: PASS`
* `REAL_DISCORD_POLICY_METRICS_SMOKE: PASS`
* `REAL_DISCORD_DELIVERY_FILTER_VERIFY: PASS`

Expected (real Discord env present):

* Internal events publish into `stream.notifications` but
  `notification-worker /status.real_delivery_blocked_count` rises by
  one per event, `real_delivery_allowed_count` rises by one for the
  allowlisted `discord.real_test_sent` event, and the real Discord
  channel sees exactly that one message.

The policy contract + every env knob is documented in
[`real-discord-delivery-policy.md`](./real-discord-delivery-policy.md).

## 17m. Tamper-evident audit chain (Stage 34)

Stage 34 hardens the audit trail. The audit-worker computes per-row
canonical payload hashes + row hashes (SHA-256) and (optionally) an
HMAC-SHA256 signature, written to `audit_integrity_records`. A
sibling table `audit_chain_verification_runs` records every
verify-chain pass.

```bash
./scripts/backfill_audit_integrity.sh
./scripts/verify_audit_integrity.sh
./scripts/simulate_audit_tamper_detection.sh
./scripts/verify_tamper_evident_audit.sh
./scripts/check_runtime_state.sh | grep -E 'AUDIT_INTEGRITY|AUDIT_RECEIPT|AUDIT_TAMPER'
```

Expected:

* `AUDIT_INTEGRITY_BACKFILL: PASS` (idempotent; re-runs report
  `created=0`).
* `AUDIT_INTEGRITY_VERIFY: PASS` (or `PASS (partial)` if there are
  audit_logs rows without integrity records -- rerun backfill).
* `AUDIT_TAMPER_DETECTION_SMOKE: PASS` (mutation is rolled back
  inside a savepoint; the real chain is untouched).
* `TAMPER_EVIDENT_AUDIT_VERIFY: PASS` -- master verifier ends green.
* `AUDIT_INTEGRITY_BACKFILL_SMOKE`, `AUDIT_INTEGRITY_VERIFY_SMOKE`,
  `AUDIT_RECEIPT_SMOKE`, `AUDIT_TAMPER_DETECTION_SMOKE`,
  `AUDIT_INTEGRITY_OPERATIONS_SMOKE`,
  `AUDIT_INTEGRITY_SAFETY_SMOKE`,
  `AUDIT_INTEGRITY_METRICS_SMOKE`,
  `AUDIT_INTEGRITY_NO_LOOP_SMOKE` -- all PASS in
  `check_runtime_state.sh`.

Operator surfaces:

* `GET /operations/audit/integrity` -- chain summary.
* `POST /operations/audit/verify-chain` -- runs the verifier.
* `GET /operations/audit/verify-chain/latest` -- the most recent run.
* `GET /operations/audit/receipt/{audit_log_id}` -- per-row receipt
  (never returns the full HMAC signature, only an 8-char preview).

The HMAC key (`AUDIT_HMAC_KEY`) is optional. Without it the chain
still detects every tamper category. Setting the key enables signed
receipts; the key value is never logged or returned by any
operations endpoint. See
[`tamper-evident-audit.md`](./tamper-evident-audit.md) for the threat
model + key-rotation roadmap.

## 17n. LLM cost governance + real LLM plan-only pilot (Stage 35)

Stage 35 makes every real LLM call go through a budget gate and
opens a narrow plan-only pilot.

```bash
./scripts/check_llm_runtime_inputs.sh        # presence only; never prints key values
./scripts/verify_llm_cost_governance.sh      # always exercises mock + cap paths
./scripts/verify_real_llm_plan_only_pilot.sh # SKIPPED when real env absent
./scripts/check_runtime_state.sh | grep -E 'LLM_BUDGET|REAL_LLM_PLAN|LLM_NO_'
```

Expected (default test cluster, mock provider, no real LLM env):

* `LLM_BUDGET_POLICY_SMOKE: PASS` (Stage 35 tables present after
  migration 013).
* `LLM_BUDGET_PREFLIGHT_ALLOW_SMOKE: PASS` (mock provider is exempt).
* `LLM_BUDGET_PREFLIGHT_BLOCK_SMOKE: PASS` (real provider with no
  active policy blocks).
* `REAL_LLM_PLAN_ONLY_GUARD_SMOKE: PASS`.
* `REAL_LLM_PLAN_ONLY_SKIPPED_SMOKE: PASS`.
* `LLM_NO_PATCH_REAL_PROVIDER_SMOKE: PASS`.
* `LLM_NO_WORKSPACE_WRITE_SMOKE: PASS` -- `/operations/safety`
  pins `llm_workspace_write_enabled=false` +
  `llm_patch_generation_enabled=false`.
* `LLM_BUDGET_OPERATIONS_SMOKE: PASS`,
  `LLM_COST_AUDIT_SMOKE: PASS`,
  `LLM_COST_NOTIFICATION_SMOKE: PASS`,
  `LLM_COST_METRICS_SMOKE: PASS`.
* `LLM_COST_GOVERNANCE_VERIFY: PASS`.
* `REAL_LLM_PLAN_ONLY_PILOT_VERIFY: PASS` (with skipped sections).

Expected (real LLM env present): the pilot script issues ONE
`generate_development_plan`, records actual usage, then asserts
`code_workspaces`, `code_change_artifacts`, and `pr_draft_artifacts`
all carry zero rows for the task -- the plan-only path created NO
writes outside of `llm_interactions`, `llm_proposal_artifacts`
(`proposal_type=development_plan_only`), `llm_usage_records`, and
`llm_budget_events`. See
[`llm-cost-governance.md`](./llm-cost-governance.md) and
[`real-llm-plan-only-pilot.md`](./real-llm-plan-only-pilot.md).

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
