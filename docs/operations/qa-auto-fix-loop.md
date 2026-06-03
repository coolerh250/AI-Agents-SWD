# QA-Guided Validation & Auto-Fix Loop (Stage 29)

Stage 29 promotes the qa-agent from a pure mock into a deterministic
gatekeeper for the controlled workspace. After Stage 28's
development-agent produces the workspace + artifacts + PR draft, the
qa-agent loads them, runs a fixed set of rules, persists a
`qa_validation_runs` row + per-rule `qa_findings`, and either lets the
pipeline finish, files an `auto_fix_request` against the
development-agent's auto-fix consumer, or blocks the workflow for
human review.

No LLM is invoked anywhere. No real GitHub write happens. No
production deploy is allowed.

## QA validation lifecycle

```
started ──► passed   ──► (devops-agent finishes pipeline)
       └──► auto_fix_requested ──► auto-fix completes ──► re-validate
       └──► blocked_for_human_review (workflow halts)
       └──► canceled / failed
```

* **started** — `qa_validation_runs` row exists; rules are running.
* **passed** — no blocking findings (severity ∈ {error, critical});
  publish `qa.completed` to `stream.deployments`.
* **auto_fix_requested** — at least one auto-fixable blocking
  finding AND `auto_fix_attempts < max_auto_fix_attempts`; publish
  `code.auto_fix_request` to `stream.development.autofix` and
  `qa.auto_fix_requested` back onto `stream.qa`.
* **blocked_for_human_review** — at least one non-auto-fixable
  blocking finding (security / policy / regression), OR
  `auto_fix_attempts >= max_auto_fix_attempts`. Workflow halts;
  `production_executed=false` is preserved.
* **canceled / failed** — reserved; not emitted by the current
  pipeline.

## Finding categories

| Category        | Auto-fixable? | Notes                                                       |
| --------------- | ------------- | ----------------------------------------------------------- |
| `syntax`        | yes           | `py_compile` failures, missing artifact files               |
| `test`          | yes           | demo-API app file without a matching generated test         |
| `documentation` | yes           | PR draft body missing one or more required sections         |
| `acceptance`    | no            | acceptance criteria don't match what the workspace delivered |
| `policy`        | no            | a denied path slipped past the generator                    |
| `security`      | no            | secret-like content or a destructive shell / SQL payload    |
| `regression`    | no            | reserved for QA-detected regressions (post-Stage 29)         |
| `unknown`       | no            | catch-all                                                   |

Severities: `info` / `warning` / `error` / `critical`. The blocking
set is `{error, critical}`.

## Deterministic auto-fixes

The development-agent's `CodeAutoFixAgent` consumer handles three
deterministic fix strategies:

| Strategy                          | Trigger finding                       | Behaviour                                                                                  |
| --------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| `append_pr_draft_sections`        | `documentation` + `missing_sections`  | Append the missing section headers with safe placeholder bodies                            |
| `regenerate_workspace_files` (test) | `test` (auto_fixable=true)           | Re-run the deterministic generator; persist the re-written app + test files                |
| `regenerate_workspace_files` (syntax) | `syntax` (auto_fixable=true)        | Same as above but driven by a `py_compile` failure                                         |

Anything outside those three buckets is refused:

* `category == "security"` (e.g. secret literal, destructive diff) →
  always blocked.
* `category == "policy"` (e.g. denied path) → always blocked.
* `category == "regression"` → always blocked.
* `category == "acceptance"` → always blocked (the qa-agent doesn't
  guess what the operator wanted).
* missing `work_item` → blocked (the regenerator needs the original
  request).

When the auto-fix completes (or fails), the consumer publishes a
`development.auto_fix_completed` / `development.auto_fix_failed` event
onto `stream.qa`. The qa-agent re-runs validation; if the rules now
pass the workflow advances, otherwise the loop guard kicks in.

## Loop guard

`QA_MAX_AUTO_FIX_ATTEMPTS` (default `2`, clamped to `[1, 10]`) caps the
loop:

* `auto_fix_attempts < max_auto_fix_attempts` AND finding is
  auto-fixable → file `auto_fix_request`, status `requested`.
* `auto_fix_attempts >= max_auto_fix_attempts` → block, even when the
  finding is auto-fixable. `final_result = blocked`,
  `reason = max_attempts_exceeded`.

## Operator commands

```
# List recent validation runs
curl -s http://localhost:8000/operations/qa/runs | jq

# Drill into a task
curl -s http://localhost:8000/operations/qa/runs/<task_id> | jq

# Inspect findings
curl -s http://localhost:8000/operations/qa/findings/<task_id> | jq

# Auto-fix request history
curl -s http://localhost:8000/operations/qa/auto-fix/<task_id> | jq

# Workflow-embedded qa_validation section
curl -s http://localhost:8000/operations/workflows/<task_id> \
  | jq '.qa_validation'

# Discord-side status snapshot
curl -s http://localhost:8007/discord/tasks/<task_id> \
  | jq '{qa_status,qa_final_result,qa_findings_count,blocking_findings_count,
         auto_fix_attempts,blocked_for_human_review}'
```

## Audit decision types (Stage 29)

| decision_type                  | When                                                  |
| ------------------------------ | ----------------------------------------------------- |
| `qa_validation_started`        | every `qa_validation_runs` row inserted               |
| `qa_validation_passed`         | run ended with `final_result=pass`                    |
| `qa_validation_failed`         | run ended with `final_result=fail` (reserved)         |
| `qa_auto_fix_requested`        | auto-fix request filed                                |
| `qa_blocked_for_human_review`  | workflow halted by the qa-agent                       |
| `code_auto_fix_completed`      | dev-agent applied at least one deterministic fix      |
| `code_auto_fix_failed`         | dev-agent refused every finding (non-auto-fixable etc.) |

`artifact_refs` carries `qa_run_id`, `fix_request_id`,
`workspace_id`, `attempt_number`, `max_auto_fix_attempts`,
`final_result`, and **always** `production_executed=false`.

## Notification event types (Stage 29)

| event_type                       | Meaning                                              |
| -------------------------------- | ---------------------------------------------------- |
| `qa.validation_started`          | qa-agent started a validation run                    |
| `qa.validation_passed`           | qa-agent passed validation                           |
| `qa.validation_failed`           | reserved                                             |
| `qa.auto_fix_requested`          | auto-fix request filed                               |
| `qa.blocked_for_human_review`    | workflow halted                                      |
| `code.auto_fix_completed`        | dev-agent applied fixes; QA will re-validate         |
| `code.auto_fix_failed`           | dev-agent refused every finding                      |

Deliveries land in `notification_deliveries` as `sandbox: true`.

## Metrics labels

| Counter                                | Labels                                              |
| -------------------------------------- | --------------------------------------------------- |
| `qa_validation_runs_total`             | `status`                                            |
| `qa_validation_passed_total`           | —                                                   |
| `qa_validation_failed_total`           | `reason`                                            |
| `qa_findings_total`                    | `severity`, `category`, `auto_fixable`              |
| `qa_auto_fix_requests_total`           | `status`                                            |
| `qa_blocked_for_human_review_total`    | `reason`                                            |
| `qa_auto_fix_attempts_total`           | `result`                                            |

## Tracing spans

| Span name                  | Notes                                              |
| -------------------------- | -------------------------------------------------- |
| `qa.validation_start`      | DB insert into `qa_validation_runs`                |
| `qa.load_code_artifacts`   | workspace + artifacts + PR draft + work item fetch |
| `qa.apply_rule`            | deterministic rule sweep                           |
| `qa.create_finding`        | DB insert into `qa_findings`                       |
| `qa.request_auto_fix`      | DB insert into `auto_fix_requests`                 |
| `qa.validation_complete`   | (reserved)                                         |
| `code.auto_fix_start`      | dev-agent auto-fix entry                           |
| `code.auto_fix_apply`      | per-finding dispatch loop                          |
| `code.auto_fix_complete`   | dev-agent auto-fix exit                            |

Each span carries `task_id`, `workflow_id`, `qa_run_id`,
`workspace_id`, `attempt_number`, `finding_count`, and the
deterministic decision attributes (severity / category /
auto_fixable) where relevant.

## Workflow gate stages (Stage 29 additions)

| stage                       | Trigger event                            | Meaning                                         |
| --------------------------- | ---------------------------------------- | ----------------------------------------------- |
| `qa_auto_fix`               | `qa.auto_fix_requested`                  | dev-agent is mid-fix; do NOT advance pipeline   |
| `blocked_for_human_review`  | `qa.blocked_for_human_review`            | workflow halted; operator must take over        |
| `in_progress` (kept)        | `qa.completed` / `development.auto_fix_completed` | normal pipeline advance                  |

`devops.deployment_simulated` continues to move the workflow to
`completed`; the gate ensures it can ONLY arrive after a
`qa.completed`.

## Why generated artifacts still aren't auto-committed

Auto-fixes write into the same `$DEVELOPMENT_AGENT_WORKSPACE_ROOT`
the Stage 28 generator uses (default `/tmp/aiagents-workspaces/<task_id>`
inside the dev-agent container). `.gitignore` blocks
`.workspaces/` + `.workspaces/**` so an operator who points the
workspace root at the working tree still doesn't commit artifacts.
Reviewers consume the diff via `/operations/code/pr-drafts/<task_id>`
and port the code manually.

## Current limitations

* The auto-fix dispatcher is deliberately narrow. A finding outside
  the three deterministic categories is blocked; a real LLM-driven
  patch is out of scope.
* `validate_acceptance_alignment` is a coarse keyword check; an
  operator must still inspect the artifacts.
* The qa-agent never changes the work item's `execution_mode`; that
  remains a Stage 27 decision.
* Loop guard is hard-clamped at `[1, 10]`. Raising it does not change
  the policy that security / policy / regression findings always
  block.

## See also

* [`docs/operations/controlled-code-generation.md`](controlled-code-generation.md)
  — Stage 28 workspace + PR draft pipeline.
* [`docs/operations/flexible-task-execution-loop.md`](flexible-task-execution-loop.md)
  — Stage 27 task lifecycle.
* `scripts/verify_qa_auto_fix_loop.sh` — 3-scenario verifier (pass /
  auto-fix loop / blocked).
