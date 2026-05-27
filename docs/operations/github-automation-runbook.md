# GitHub Automation Runbook

Operator runbook for the `github-automation` service (port `8005`,
package `apps/github-automation/`). The service runs **dry-run by
default**: every call returns a deterministic mock response and contacts
no real GitHub API unless the caller explicitly sets `dry_run=false`
*and* the container has a `GITHUB_TOKEN` env var.

> Safety contract: this service never merges a PR, never modifies branch
> protection, never deploys to production, and never stores a token in
> the repository. Real-GitHub calls are opt-in only and require both
> `GITHUB_TOKEN` and `RUN_REAL_GITHUB_TEST=true`. PR titles for opt-in
> runs are forced to begin with `[AI-Agents-SWD Test]`.

---

## 1. Service overview

| Field            | Value                                                       |
|------------------|-------------------------------------------------------------|
| Service name     | `github-automation`                                         |
| Port             | `127.0.0.1:8005`                                            |
| Default repo     | `coolerh250/AI-Agents-SWD`                                  |
| Default dry-run  | `true` (`GITHUB_DRY_RUN=true`)                              |
| Token source     | `GITHUB_TOKEN` env var only — never read from any file      |
| SDK              | `shared/sdk/github/` (`GitHubClient`)                       |
| Gateway proxy    | `POST /github/demo-pr` on communication-gateway (`:8004`)   |

---

## 2. Verify dry-run

From the test server (`10.0.1.31`):

```
./scripts/verify_github_automation.sh
```

Expected final lines:

```
checks passed: 7 / 7
GITHUB_AUTOMATION_VERIFY: PASS
VERIFY_GITHUB_AUTOMATION_DONE
```

Or run the inline smokes inside `check_runtime_state.sh`:

```
./scripts/check_runtime_state.sh | grep GITHUB_
```

Expected (Stage 18 adds the six `GITHUB_PIPELINE_*` smokes on top of
the Stage 17 service-level ones):

```
GITHUB_AUTOMATION_HEALTH: PASS
GITHUB_DEMO_PR_DRY_RUN_SMOKE: PASS
GITHUB_AUDIT_SMOKE: PASS
GITHUB_NOTIFICATION_SMOKE: PASS
GITHUB_METRICS_SMOKE: PASS
GITHUB_PIPELINE_INTEGRATION_SMOKE: PASS
GITHUB_WORKFLOW_RESULT_SMOKE: PASS
GITHUB_TIMELINE_SMOKE: PASS
GITHUB_PIPELINE_AUDIT_SMOKE: PASS
GITHUB_PIPELINE_NOTIFICATION_SMOKE: PASS
GITHUB_PIPELINE_TRACE_SMOKE: PASS
```

## 2a. Verify pipeline-triggered dry-run PR

The Stage 18 integration drives a workflow end-to-end through
`communication-gateway → orchestrator → agents → github-automation`
and asserts the github result lands in workflow state / timeline /
audit / notifications / Tempo trace:

```
./scripts/verify_github_pipeline_flow.sh
```

Expected last lines:

```
checks passed: 7 / 7
GITHUB_PIPELINE_FLOW_VERIFY: PASS
VERIFY_GITHUB_PIPELINE_FLOW_DONE
```

To trigger one manually:

```
task=github-manual-$(date +%s)
curl -sS -X POST http://localhost:8004/intake/mock -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$task\",\"request\":{\"type\":\"dev.test\",\"github\":{\"enabled\":true,\"dry_run\":true}}}"
```

Then watch the workflow:

```
curl -sS "http://localhost:8000/workflow/progress/$task" | python3 -m json.tool
curl -sS "http://localhost:8000/workflow/timeline/$task" | python3 -m json.tool
```

`progress.pr_url` is the canonical handle. `progress.github_status`
will be `success` for a healthy dry-run, `failed` if
github-automation was unreachable, or `disabled` when
`request.github.enabled=false`.

---

## 3. Configure `GITHUB_TOKEN`

The token is **never** committed. Inject it via Docker Compose env at
container start:

```
GITHUB_TOKEN=ghp_REPLACE_ME RUN_REAL_GITHUB_TEST=true \
  docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate github-automation
```

Or set the env var in your shell and have Compose pick it up via the
`${GITHUB_TOKEN:-}` interpolation in `infra/docker-compose/docker-compose.yml`.

The Compose file references `${GITHUB_TOKEN:-}` only — there is no
default value baked in. If the env var is unset the container starts
with an empty token and refuses any `dry_run=false` call with a
`GitHubMissingTokenError`.

The token is never:
* committed to git;
* echoed in API responses;
* logged at any log level;
* written to `source/progress.md`, `docs/`, or any artifact.

---

## 4. Run a real GitHub test (opt-in only)

This is the **only** code path that issues real GitHub write calls.
Required preconditions:

1. `GITHUB_TOKEN` env var is set and reaches the `github-automation`
   container.
2. `RUN_REAL_GITHUB_TEST=true` env var is set (the verify script
   refuses to make real calls otherwise).
3. The token's repo scope covers `coolerh250/AI-Agents-SWD` (or
   whichever repo you target via `GITHUB_DEFAULT_REPO`).

Run:

```
RUN_REAL_GITHUB_TEST=true GITHUB_TOKEN=$GITHUB_TOKEN \
  ./scripts/verify_github_automation.sh
```

The script appends an extra section after the dry-run checks. It calls
`POST /github/workflow/demo-pr` with `dry_run=false`, which creates a
real issue, a real branch (`ai-agents-swd/real-<ts>`), one real file
commit (`docs/automation-demo.md`), one real PR — and stops. The output
ends with:

```
REAL_GITHUB_TEST_PR_URL=https://github.com/coolerh250/AI-Agents-SWD/pull/<number>
```

The PR title is forced to begin with `[AI-Agents-SWD Test]`. The script
**never** merges or closes the PR; that is up to the operator.

---

## 5. Confirm no merge happened

```
gh pr view <number> --json state,merged
```

`state` must be `OPEN` and `merged` must be `false`. The service does
not call `merge` / `update_pull_request` / branch-protection endpoints.
A reviewer can search the codebase to confirm:

```
grep -rni "merge\|protection" shared/sdk/github/ apps/github-automation/
```

Should return nothing destructive — only logging strings and runbook
references.

---

## 6. Confirm no production action

Same guarantee as every other service:

```
docker compose -f infra/docker-compose/docker-compose.yml \
  exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT COUNT(*) FROM deployment_records
    WHERE metadata->>'production_executed'='true' OR environment='production';"
```

Must return `0`. The github-automation service does not write
deployment_records; the production_executed counter is owned by the
devops-agent and remains false in test.

---

## 7. Inspect audit trail

Every demo-pr (dry-run or real) writes one audit row with
`decision_type='github_automation'`:

```
curl -s http://localhost:8003/audit/events/<task_id> | python3 -m json.tool
```

The `artifact_refs` field carries `issue_url`, `branch`, `pr_url`,
`dry_run`. For dry-run rows the URLs are `https://github.com/.../1234`
style mocks; for real rows they are the actual GitHub URLs.

---

## 8. Inspect notifications

```
curl -s "http://localhost:8004/notifications?count=200" \
  | python3 -m json.tool \
  | grep -E '"event_type"|"task_id"|"github"' | head -40
```

The event_type is `github.pr.dry_run` for dry-run and
`github.pr.created` for real runs. The payload also carries an explicit
`dry_run: true|false` flag on the notification itself.

---

## 9. Inspect a trace

`github-automation` is OTel-instrumented and emits spans for every
operation. Open Grafana → Explore → Tempo and search by `task_id`
attribute. Span names to look for:

```
github.demo_pr
github.create_issue
github.create_branch
github.create_or_update_file
github.create_pull_request
github.read_checks
github_automation.demo_pr        # client-side (e.g. from communication-gateway)
```

Each span carries `github.repo`, `github.operation`, `github.dry_run`,
`task_id`, `workflow_id` attributes.

---

## 10. Rollback a test branch / PR

For dry-run runs there is nothing to roll back — no real GitHub state
changed.

For an opt-in real run that you want to undo:

```
gh pr close <number>
gh api -X DELETE /repos/coolerh250/AI-Agents-SWD/git/refs/heads/ai-agents-swd/real-<ts>
gh api -X DELETE /repos/coolerh250/AI-Agents-SWD/contents/docs/automation-demo.md \
  -f message="rollback: real github automation verify" \
  -f sha=<sha>
```

If the test file was only modified on the test branch and the branch
was deleted, the file delete on `main` is not required.

---

## 11. Common issues

### `dry_run=false` but `GitHubMissingTokenError`

The container started without `GITHUB_TOKEN`. Re-export and recreate:

```
export GITHUB_TOKEN=ghp_...
docker compose -f infra/docker-compose/docker-compose.yml \
  up -d --force-recreate github-automation
docker compose exec -T github-automation env | grep '^GITHUB_'
```

### Token leaked in logs

This should never happen — the client refuses to put the token in any
return value. If you ever see it in logs, treat it as an incident:
rotate the token at GitHub, restart `github-automation`, run

```
grep -rn "ghp_\|github_pat_" docs/ source/ apps/ shared/ infra/ scripts/ tests/
```

and confirm the only matches are placeholders.

### Demo PR succeeds but no notification / audit appears

Both are best-effort and gated on Redis / audit-service being reachable.
Check:

```
docker compose -f infra/docker-compose/docker-compose.yml ps redis audit-service
curl -s http://localhost:6379/ping  # no — use redis-cli below
docker compose exec -T redis redis-cli ping
curl -s http://localhost:8003/health
```

If both are healthy and the events still don't appear, the cluster is
probably racing — `verify_github_automation.sh` polls for ~10 seconds.

### `GITHUB_AUTOMATION_HEALTH: FAIL`

```
docker compose logs --tail=200 github-automation
```

Most common cause: the service container hasn't picked up the new
build. `docker compose build github-automation && docker compose up -d --force-recreate github-automation`.

---

## 12. What this service does NOT do

* Merge PRs.
* Modify branch protection.
* Touch `main` directly (write or delete).
* Deploy to production.
* Call any non-GitHub external SaaS.
* Read secrets from disk or Vault. (The Vault dev container in the
  Compose stack is unrelated.)
* Echo `GITHUB_TOKEN` in any response, log, or artifact.
