# Failure / Governance Scenario Matrix (Step 65H.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — no scenario below is executed in this stage.**

Scenario matrix for Step 65H. Each scenario is controlled and non-external by default; entry points
are the real routes mapped in [failure-governance-validation-plan.md](failure-governance-validation-plan.md).
Columns: EP = entry point · Ext = external action allowed · prod = `production_executed_true_count`
expectation · Risk (see [failure-governance-risk-register.md](failure-governance-risk-register.md)).

## A. Approval / governance scenarios (65H.2)
| ID | Scenario | EP | Expected policy decision | Expected approval state | Audit / evidence | Ext | prod | Risk | Abort if |
|---|---|---|---|---|---|---|---|---|---|
| A1 | approval **required** | `/workflow/test` restricted request → policy-engine | `approval_required=true` | `pending` | `approval_requested` audit; `/task-graph` approval_status | no | 0 | MEDIUM | approval not required for a restricted request |
| A2 | approval **granted** | `/approval/approve` → resume | allowed after approve | `approved` → workflow resumes | `approval_granted`; `/audit-evidence` | no | 0 | HIGH | resume performs any external write |
| A3 | approval **denied** | `/approval/reject` | blocked | `rejected` (terminal) | `approval_denied`; workflow not resumed | no | 0 | HIGH | denied workflow still proceeds |
| A4 | approval **expired / timeout** | aged `pending` request (mechanism TBC at 65H.2) | not resumed | `pending`→`expired` (to confirm) | expiry audit if present | no | 0 | HIGH | expired request auto-approves |
| A5 | operator action **audit** | `/operations/approval-decisions/{task_id}` (read) | n/a | recorded decision | operator-action audit event | no | 0 | LOW | decision missing from audit |
| A6 | production action **blocked** | production-effect work item / restricted action | `approval_required`; hard policy blocks direct dispatch | routed to `waiting_approval` | block audit; `/safety` unchanged | no | 0 | HIGH | production action executes (prod≠0) |

## B. Cancel / abort / ignore-after-abort scenarios (65H.3)
| ID | Scenario | EP | Expected result | Audit / evidence | Ext | prod | Risk | Abort if |
|---|---|---|---|---|---|---|---|---|
| B1 | cancel **before execution** | `/workflow/test` (create) → `/workflow/cancel/{id}` | stage `canceled`, `production_executed=false` | `workflow.canceled` audit; `/task-graph` | no | 0 | HIGH | cancel triggers external action |
| B2 | cancel **during** workflow | cancel a non-terminal workflow | stage `canceled` | canceled audit | no | 0 | HIGH | workflow keeps running after cancel |
| B3 | abort **during** workflow | `/workflow/abort/{id}` | stage `aborted`, `production_executed=false` | `workflow.aborted` audit | no | 0 | HIGH | abort triggers external action |
| B4 | **ignore-after-abort** | cancel/abort an already-terminal workflow | **HTTP 409** refused | no state change | no | 0 | MEDIUM | a terminal workflow is re-terminated |
| B5 | **late event ignored after abort** | deliver a stage event after abort | event ignored; stage stays `aborted` | no new agent execution | no | 0 | HIGH | late event resumes the workflow |
| B6 | Admin Console status visibility | `/task-graph` + `/audit-evidence` (read) | canceled/aborted visible | audit timeline | no | 0 | LOW | status not visible on formal pages |

## C. Retry / DLQ / replay / terminal-failure scenarios (65H.4)
| ID | Scenario | EP | Expected result | Audit / evidence | Ext | prod | Risk | Abort if |
|---|---|---|---|---|---|---|---|---|
| C1 | controlled agent **failure** | inject a failing event (controlled, non-external) | retry attempted up to `max_retries=3` | retry audit; `/operations/dlq` | no | 0 | HIGH | failure injection causes external write |
| C2 | **retry scheduler** handling | retry-scheduler consumes failures | retry count increments to limit | retry_timeline on `/task-graph` | no | 0 | HIGH | retry storm (unbounded) |
| C3 | **DLQ creation** | `retry_count >= 3` | event moves to `stream.deadletter` | `/operations/dlq` `deadletter_count` | no | 0 | HIGH | DLQ never created |
| C4 | **manual DLQ replay** | `POST /deadletter/replay/{message_id}` | one controlled replay | replay audit | no | 0 | HIGH | replay exceeds authorized count |
| C5 | **terminal failure** state | exhausted retries | `stream.deadletter.terminal`; terminal_count | terminal evidence | no | 0 | HIGH | terminal state not recorded |
| C6 | **retry count limit** | verify `max_retries=3` respected | no retry beyond 3 | retry_timeline | no | 0 | MEDIUM | retries exceed limit |
| C7 | **failure evidence visibility** | `/audit-evidence` + `/task-graph` (read) | failure visible | audit + retry timeline | no | 0 | LOW | evidence not visible |

## D. Safety / no-production scenarios (spans 65H.2/65H.4)
| ID | Scenario | EP | Expected result | Ext | prod | Risk | Abort if |
|---|---|---|---|---|---|---|---|
| D1 | production-effect task **blocked** | create production-effect work item | routed to `waiting_approval`; not dispatched | no | 0 | HIGH | it dispatches / executes |
| D2 | production **deployment blocked** | attempt a production deploy path | blocked by hard policy | no | 0 | HIGH | any deploy occurs |
| D3 | `production_executed_true_count` remains **0** | `/operations/safety` (read) before/after every scenario | stays 0 | no | 0 | LOW | counter changes |
| D4 | external write **blocked when not authorized** | attempt an external rail without enabling its flag | blocked (guard/kill switch) | no | 0 | HIGH | an unauthorized external write succeeds |
| D5 | **kill switch effectiveness** | confirm each external flag disabled at rest | all disabled | no | 0 | LOW | a kill switch is ineffective |

## This stage's posture
Planning only. No scenario executed; no workflow execution; no external write; no LLM call; no
Discord send; no production action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
