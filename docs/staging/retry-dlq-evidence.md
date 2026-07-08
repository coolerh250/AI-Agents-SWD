# Retry / DLQ — Evidence (Step 65H.4)

> **Staging only — non-production only. No production action. No production data.**
> **Read-only evidence (ids/metadata). No secret value printed.**

Evidence for the Step 65H.4 controlled retry / DLQ / manual-replay / terminal-failure run.

## Per-scenario evidence
| Scenario | task_id | trigger | outcome |
|---|---|---|---|
| S1 DLQ + replay | `step65h4-s1-dlq-replay-…` | `simulate_failure=true` | dead-lettered (retry_count 3,4) → 1 manual replay |
| S2 terminal | `step65h4-s2-terminal-…` | `simulate_failure=true` | terminal failure → workflow `failed` + sev2 incident |

## Retry / DLQ metrics (`/operations/dlq`)
- Baseline (before): `deadletter_length=0`, `deadletter_terminal_length=0`.
- After: `deadletter_length=5`, `deadletter_terminal_length=3` — **stable across a 4s re-check**
  (bounded loops settled; no runaway).
- Distinct dead-letter `retry_count` values: **[3, 4]** (dead-letter at max_retries=3; terminal at >3).

## Manual replay (`POST :18015/deadletter/replay/{message_id}`)
- `message_id=1783472430724-0` → `replayed=true`, `stream=stream.development`,
  `published_id=1783472476560-0`, `task_id=step65h4-s1-dlq-replay-…`. Exactly **1** replay.

## Terminal failure (S2)
- `stream.deadletter.terminal` received the S2 terminal event.
- Workflow_state: `stage=failed`, `execution_result.status=failed`, `production_executed=false`,
  `failure_reason="development-agent simulated failure … (request.simulate_failure)"`.
- Agent executions (S2): 6 rows — 4 `failed` (development-agent retries) + intake/requirement
  `completed`.
- Audit timeline (S2): 9 events, 3 failure-related (`workflow_failed`).

## Incidents (`/operations/incidents`)
- 3 sev2 incidents from `retry-scheduler` for the controlled-test tasks (S1 ×2, S2 ×1), status
  `open` — expected controlled-test artifacts (the operator may close them).

## Safety snapshot
- Before / after: `production_executed_true_count=0`; github/discord/llm external all `false`;
  `hard_policy_enforced=true`.

## No secrets / no external / no injection
- No secret value printed, logged, or committed. No GitHub write, no Discord send, no LLM call. The
  controlled failure used the platform's built-in `request.simulate_failure` switch — no DB
  manipulation, no unsafe stream injection.

## Status
Step 65H.4: **PASS** (operator UI validation pending). `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
