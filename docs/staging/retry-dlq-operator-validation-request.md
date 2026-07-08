# Retry / DLQ — Operator Validation Request (Step 65H.4)

> **Staging only — non-production only. No production action. No production data.**
> **Claude Code does not decide staging functional acceptance. This document requests the operator's UI validation.**

Step 65H.4 completed technically; API evidence is captured. The operator must confirm the evidence on
the **formal** Admin Console pages / APIs (not `/demo-evidence`).

## Evidence surfaces — Admin Console UI pages vs backend APIs
> **Correction:** the DLQ / incidents evidence is split between Admin Console **UI pages** (under
> `/admin/…`) and **backend read-only JSON APIs** (under `:18000/operations/…`). There is **no
> dedicated DLQ UI page** — the DLQ counts are an API only (the documented "no `/dlq` page" gap).

### Admin Console UI pages (`/admin/…`)
| Page | Look for | Expected |
|---|---|---|
| `/admin/incidents` | retry-scheduler incidents summary | 3 sev2 controlled-test incidents (S1 ×2, S2 ×1) |
| `/admin/task-graph` | S2 `step65h4-s2-terminal-…` | stage `failed` (failure_reason = simulated failure) |
| `/admin/agent-executions` | S2 task id | development-agent `failed` retries + intake/requirement `completed` |
| `/admin/audit-evidence` | S1/S2 task ids | `workflow_failed` audit events |
| `/admin/safety` | production-executed counter | `production_executed_true_count=0`; external integrations disabled |
| `/admin/metrics` | (supporting) | retry / deadletter metrics; no external side effect |

### Backend read-only APIs (no UI page — open the URL directly, or via SSH tunnel)
| API | Look for | Live value (captured read-only) |
|---|---|---|
| `:18000/operations/dlq` | DLQ / terminal counts (**API only — no `/dlq` page**) | `deadletter_length=5`, `deadletter_terminal_length=3`; retry_count ∈ {3,4} |
| `:18000/operations/incidents` | per-task incident detail (backs the `/admin/incidents` page) | 3 sev2 `retry-scheduler` incidents for `step65h4-*` |
| `:18015/deadletter/replay/{id}` result | (already run once) | `replayed=true`, re-published to `stream.development` |

## Required operator response
Record one of:
- **VISIBLE** — the retry / DLQ / manual-replay / terminal-failure evidence is visible.
- **NOT_VISIBLE** — evidence not visible.
- **PARTIAL_WITH_GAPS** — some visible; note which are missing.

## Note on incidents
The 3 sev2 incidents are expected controlled-test artifacts (open). The operator may close them; no
action is required for acceptance beyond acknowledging them.

## Rule
Claude Code must not self-accept this validation or decide staging functional acceptance (that is the
Step 65I operator verdict). Until the operator responds, Step 65H.4 remains **PASS** with operator UI
validation pending.

## Status
Step 65H.4: awaiting operator UI validation. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
