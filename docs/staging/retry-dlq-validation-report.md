# Retry / DLQ / Manual Replay Validation Report (Step 65H.4)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Controlled failure test via the platform's built-in `simulate_failure` switch. No external GitHub / Discord / LLM action. No production action.**

Records the **real** controlled retry / DLQ / manual-replay / terminal-failure validation on staging
`10.0.1.32`, under operator authorization: two controlled-failure workflows exercised the retry
scheduler, DLQ creation, one manual replay, the retry-count limit, and terminal failure. No external
integration was used; no DB manipulation; no unsafe stream injection.

## Overall result
- Overall result: **PASS_WITH_GAPS** — all authorized retry/DLQ/replay/terminal paths validated using
  the platform's built-in controlled-failure mechanism; the retry loops were bounded and settled
  (no runaway). **Operator confirmed VISIBLE with a gap** (`PARTIAL_WITH_GAPS`): the DLQ is not
  surfaced on any Admin Console page — its counts/queue are backend-API-only. See the operator-flagged
  UX gap in [retry-dlq-known-gaps.md](retry-dlq-known-gaps.md).
- `production_executed_true_count=0` before, during, and after. **Claude Code does not decide staging
  functional acceptance.**

## Authorization compliance
| Item | Authorized | Actual |
|---|---|---|
| Controlled failure workflows | ≤ 2 | **2** |
| Max retry count | 3 | **respected** (dead-letter at retry_count=3; terminal at >3) |
| Manual DLQ replays | ≤ 1 | **1** |
| External actions (GitHub/Discord/LLM) | NO | **none** |
| Production action | forbidden | **none** |
| DB manipulation / unsafe stream injection | forbidden | **none** |
| production_executed_true_count | 0 | **0** |

## Controlled-failure mechanism (platform-safe)
- Triggered via the platform's built-in switch **`request.simulate_failure: true`**, which makes the
  distributed **development-agent** raise `SimulatedFailure` in `handle()`. This is the platform's
  existing safe controlled-failure path — **not** an unsafe stream injection and **not** DB
  manipulation. The failure flows through the normal `StreamAgent._handle_failure` → retry →
  `publish_dead_letter` path.

## Scenarios & results
### Scenario 1 — controlled failure → retry → DLQ creation → one manual replay (PASS)
- Task `step65h4-s1-dlq-replay-…` via `/workflow/test` (type `feature`, `simulate_failure=true`).
- development-agent failed → retried (retry_count 1→2→3) → **dead-lettered** to `stream.deadletter`
  (`deadletter_length` rose to ≥2; entries at retry_count=3 and 4, `original_stream=stream.development`).
- **One manual replay**: `POST :18015/deadletter/replay/{message_id}` → `replayed=true`, re-published
  to `stream.development` (`published_id` returned), `task_id` matched. Exactly **1** replay.

### Scenario 2 — repeated failure → retry limit → terminal failure (PASS)
- Task `step65h4-s2-terminal-…` via `/workflow/test` (`simulate_failure=true`).
- Reached **terminal failure** (`stream.deadletter.terminal`); the retry-scheduler created a **sev2
  incident**, published a `workflow_failed` audit event, and flipped the workflow_state to
  **`stage=failed`** (`production_executed=false`, `failure_reason` = the simulated failure).
- Agent executions for S2: 4 `failed` (development-agent retries) + intake/requirement `completed`.

## Retry-count limit & no-runaway (PASS)
- Distinct dead-letter `retry_count` values observed: **[3, 4]** — an agent dead-letters at
  `retry_count = max_retries = 3`, and the retry-scheduler marks terminal at `retry_count > 3`. No
  `retry_count` exceeded 4.
- Settle check: `deadletter_length=5`, `deadletter_terminal_length=3` were **stable across 4s** — the
  bounded retry loops self-terminated (no retry storm).

## Evidence surfaces (formal API; no dedicated `/dlq` page)
- `/operations/dlq` — `deadletter_length`, `deadletter_terminal_length`, deadletter/terminal events.
- `/operations/incidents` — 3 sev2 incidents from the retry-scheduler (S1 ×2, S2 ×1).
- `/task-graph` — S2 workflow_state `failed`.
- `/agent-executions` — the failed development-agent hops.
- `/audit-evidence` — `workflow_failed` audit events.
- `POST :18015/deadletter/replay/{id}` — the manual replay result.

## Safety
- `production_executed_true_count=0` throughout. No external write (all external flags stayed disabled
  — none were ever enabled). No runtime config change, no service recreate, no full-stack restart, no
  DB reset, no DB manipulation, no unsafe stream injection. ≤2 controlled-failure workflows; 1 manual
  replay.

## Status
- Step 65H.4: **PASS_WITH_GAPS** — operator confirmed **VISIBLE with gap** (the DLQ has no Admin
  Console page; backend-API-only). See
  [retry-dlq-operator-validation-request.md](retry-dlq-operator-validation-request.md). Not
  production readiness.

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
