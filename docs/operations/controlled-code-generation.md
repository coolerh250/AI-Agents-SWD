# Controlled Code Generation Workspace (Stage 28)

Stage 28 promotes the development-agent from a pure mock to a
**deterministic, template-based** code generator that:

* Creates a controlled workspace per Discord-driven task.
* Writes generated files into an allowlisted path tree.
* Records a per-file unified diff + SHA hashes.
* Runs local `py_compile` + diff + secret-content validation.
* Delivers a PR draft package + a GitHub dry-run PR.

No LLM is invoked. No real GitHub write happens. The operator must
port the diff manually before any merge.

## Workspace lifecycle

```
created → generating → generated → ready_for_pr_draft
                    └─ validation_failed
                    └─ blocked
                    └─ canceled
```

* **created** — row exists in `code_workspaces`; nothing written yet.
* **generating** — the deterministic generator is producing files.
* **generated / ready_for_pr_draft** — all files written + validated +
  PR draft created. devops-agent flows the draft into a dry-run PR.
* **validation_failed** — `py_compile` or diff check failed; no PR
  draft, `code.validation_failed` notification + audit emitted.
* **blocked** — classifier refused (no template hit, denied path,
  secret content, work item not ready). No files written, no PR
  draft, `code.generation_blocked` notification + audit emitted.
* **canceled** — reserved; not emitted by the current pipeline.

## Allowed paths

```
docs/generated/
apps/demo-generated/
tests/generated/
source/generated/
```

## Denied paths (always win over allowlist)

```
.github/*           .github/**
infra/*             infra/**
migrations/*        migrations/**
shared/sdk/secrets/*  shared/sdk/secrets/**
docker-compose*.yml infra/docker-compose/*
*secret*            *.pem  *.key  *.env  *.env.*
docs/operations/secrets-management.md
source/progress.md
```

`delete` changes are refused outright (`validate_change_type`). The
generator only produces `create` / `update`.

## Deterministic templates

| Trigger keyword                              | Template          | Files                                                                 |
| -------------------------------------------- | ----------------- | --------------------------------------------------------------------- |
| docs / document / readme / 文件 / 說明        | `documentation`   | `docs/generated/<task_id>.md`                                         |
| api / endpoint / service / `/healthz`         | `demo_api`        | `apps/demo-generated/<slug>_api.py` + `tests/generated/test_<slug>_api.py` |
| utility / helper / function / 工具 / 函式     | `simple_utility`  | `apps/demo-generated/<slug>_utility.py` + `tests/generated/test_<slug>_utility.py` |
| (no match)                                   | `blocked`         | —                                                                     |

When two categories collide (e.g. *"document the new API endpoint"*),
`documentation` wins, then `demo_api`, then `simple_utility`.

Every generated file embeds `task_id`, `production_executed=false`,
and `generator_mode=deterministic_template` in its body for traceability.

## Local validation

The development-agent runs three checks before publishing the PR draft:

1. **`py_compile`** on every generated `*.py` file (no execution).
2. **Diff non-empty** + at least one hunk per file.
3. **Allowlist + secret-content** check on each file (regex hit
   refuses GitHub tokens, AWS keys, PEM headers, etc.).

The combined result lands in `pr_draft_artifacts.test_results` and is
mirrored on the `code_generation` workflow section.

## PR draft delivery

`pr_draft_artifacts.body` always carries these sections:

```
## Summary
## Changed Files
## Generated Diff Summary
## Validation Result
## Risk Assessment
## Rollback Plan
## Safety Notes
```

When a PR draft exists, the devops-agent forwards `title` / `body` /
`risk_assessment` / `rollback_plan` to `github-automation
/github/workflow/demo-pr` in dry-run mode and writes the result
(`dry_run=true`, `pr_url`, `branch`, `checks_status`) back into
`pr_draft_artifacts.github_dry_run_result`.

`production_executed=false` is enforced at every layer; the demo-pr
endpoint never receives a real token call path.

## Operator commands

```
# List recent workspaces
curl -s http://localhost:8000/operations/code/workspaces | jq

# Drill into one task
curl -s http://localhost:8000/operations/code/workspaces/<task_id> | jq

# Inspect just the artifacts
curl -s http://localhost:8000/operations/code/artifacts/<task_id> | jq

# Read the PR draft body
curl -s http://localhost:8000/operations/code/pr-drafts/<task_id> \
  | jq -r '.pr_draft.body'

# Workflow-embedded code_generation section
curl -s http://localhost:8000/operations/workflows/<task_id> \
  | jq '.code_generation'

# Per-status summary counters
curl -s http://localhost:8000/operations/summary | jq '.code_generation_summary'

# Discord-side status snapshot
curl -s http://localhost:8007/discord/tasks/<task_id> | jq \
  '{code_generation_status,changed_files_count,pr_draft_status,validation_status,
    github_dry_run_pr_url,code_generation_blocked_reason}'
```

## Policy-block behaviour

When the classifier refuses:

* `code_workspaces.status = 'blocked'`
* `code_workspaces.generator_mode = 'blocked'`
* `code_workspaces.blocked_reason` carries the reason
  (`unclassifiable_description`, `work_item_status:<status>`,
  `refused:denied:<pattern>`, `refused:secret_like:<kind>`, …).
* `pr_draft_artifacts` is NOT written for this task.
* Audit row `decision_type='code_generation_blocked'` is published.
* Notification event `code.generation_blocked` is delivered.

## Audit decision types (Stage 28)

| decision_type                  | Emitted when                                         |
| ------------------------------ | ---------------------------------------------------- |
| `code_workspace_created`       | Every workspace row insert / upsert                  |
| `code_generated`               | At least one artifact written + diff recorded        |
| `code_validation_passed`       | Local validation succeeded                           |
| `code_validation_failed`       | Local validation failed                              |
| `code_pr_draft_created`        | `pr_draft_artifacts` row created with `status=ready` |
| `code_generation_blocked`      | Workspace flipped to `blocked` (classifier or policy)|

`artifact_refs` carries `workspace_id` / `changed_files` /
`generator_mode` / `validation_status` / `pr_draft_id` and
`production_executed=false`.

## Notification event types (Stage 28)

| event_type                  | Meaning                                            |
| --------------------------- | -------------------------------------------------- |
| `code.workspace_created`    | A new code workspace was created                   |
| `code.generated`            | Deterministic code generation succeeded            |
| `code.validation_passed`    | Local validation passed                            |
| `code.validation_failed`    | Local validation failed                            |
| `code.pr_draft_ready`       | PR draft package created (with risk + rollback)    |
| `code.generation_blocked`   | Classifier / policy refused the request            |

Deliveries land in `notification_deliveries` as `sandbox: true` (no
external Discord write).

## Metrics labels

| Counter                                    | Labels                                             |
| ------------------------------------------ | -------------------------------------------------- |
| `code_workspaces_total`                    | `execution_mode`, `generator_mode`, `status`       |
| `code_generation_attempts_total`           | `execution_mode`, `generator_mode`                 |
| `code_generation_success_total`            | `execution_mode`, `generator_mode`, `risk_level`   |
| `code_generation_blocked_total`            | `reason`                                           |
| `code_validation_failures_total`           | `check` (allowlist / secret_content / py_compile / diff_empty / overall) |
| `pr_draft_artifacts_total`                 | `execution_mode`, `status`, `risk_level`           |

## Tracing spans

| Span name                          | Notes                                              |
| ---------------------------------- | -------------------------------------------------- |
| `code_workspace.create`            | DB insert / upsert into `code_workspaces`          |
| `code_workspace.add_artifact`      | DB insert into `code_change_artifacts`             |
| `code_workspace.create_pr_draft`   | DB upsert into `pr_draft_artifacts`                |
| `code_generation.plan`             | Deterministic classifier                           |
| `code_generation.generate`         | Workspace write loop                               |
| `code_generation.local_validation` | py_compile + diff non-empty                        |
| `code_generation.create_pr_draft`  | PR body assembly + persistence                     |
| `devops.github_automation`         | (existing) downstream github-automation dry-run    |

Each span carries `task_id`, `workflow_id`, `workspace_id`,
`changed_files_count`, and `risk_level` attributes where applicable.

## Why generated artifacts are NOT auto-committed

The development-agent writes into
`$DEVELOPMENT_AGENT_WORKSPACE_ROOT/<task_id>/` (default
`/tmp/aiagents-workspaces/<task_id>`). The repo's `.gitignore` excludes
`.workspaces/` and `.workspaces/**` so even if an operator points the
workspace root at the working tree, the artifacts stay out of commits.

Operators review the diff via `/operations/code/pr-drafts/<task_id>`,
port the file content manually to a feature branch, run the project's
test suite, and only then open a real PR. The Stage 28 pipeline is a
**review aid**, not a code merge mechanism.

## Current limitations

* Templates are intentionally trivial. The platform has no domain
  knowledge — the deterministic body is a stub a human reviewer must
  replace.
* No QA auto-fix loop yet. If validation fails the workspace flips to
  `validation_failed` and Step 28 is expected to drive re-generation.
* Real GitHub write remains disabled. The Stage 23 controlled-real path
  is the only way to touch a live repo and it stays gated by
  `RUN_REAL_GITHUB_TEST=true` + `GITHUB_TOKEN`.
* `validate_no_destructive_change` is heuristic — a clever payload
  could slip past. Operators must still read the diff before porting.

## See also

* [`docs/operations/flexible-task-execution-loop.md`](flexible-task-execution-loop.md)
  — Stage 27 lifecycle (task_work_items / agent_discussions /
  clarification_requests).
* [`docs/operations/manual-verification.md`](manual-verification.md) —
  human-driven smoke walkthrough.
* `scripts/verify_controlled_code_generation.sh` — 3-scenario verifier
  (docs / API / policy block).
