# Failure & Governance — Validated Scenarios Summary (Step 65H.5)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only — no scenario executed in this stage.**

Per-scenario validated/tracked status across Step 65H.2–65H.4. `prod` =
`production_executed_true_count`.

## Approval / governance (65H.2)
| ID | Scenario | Result | Evidence | prod |
|---|---|---|---|---|
| A1 | approval required | VALIDATED | `waiting_approval` / `pending`; policy `approval_required=true` | 0 |
| A2 | approval granted → resume | VALIDATED | `/approval/approve` → auto-resume → `completed` (5 hops) | 0 |
| A3 | approval denied → terminal | VALIDATED | `/approval/reject` → `rejected` (terminal, not resumed) | 0 |
| A6 | production block | VALIDATED | `production.deploy` → `waiting_approval`, not dispatched, left unapproved | 0 |
| A4 | approval expired / timeout | **TRACKED GAP** | no safe route; DB manipulation forbidden; not executed | 0 |

## Cancel / abort / ignore-after-abort (65H.3)
| ID | Scenario | Result | Evidence | prod |
|---|---|---|---|---|
| B1 | cancel before execution | VALIDATED | `waiting_approval` → cancel → `canceled` (0 hops) | 0 |
| B2 | cancel during workflow | VALIDATED | dispatched → cancel → `canceled` (stuck) | 0 |
| B3 | abort during workflow | VALIDATED | `waiting_approval` → abort → `aborted` | 0 |
| B4/B5 | ignore-after-abort | VALIDATED | late re-cancel / re-abort / resume → **HTTP 409** | 0 |
| B5-raw | raw late-**stream**-event injection | **TRACKED GAP** | unsafe injection forbidden; API-level validated instead | 0 |
| — | cancel-during in-flight events | ASYNC CHARACTERISTIC | in-flight agent hops still run; workflow stays `canceled`, `production_executed=false` | 0 |

## Retry / DLQ / manual replay (65H.4)
| ID | Scenario | Result | Evidence | prod |
|---|---|---|---|---|
| C1 | controlled failure | VALIDATED | platform `request.simulate_failure=true` (development-agent) | 0 |
| C2 | retry scheduler | VALIDATED | retry_count progression 1→2→3 | 0 |
| C3 | DLQ creation | VALIDATED | `stream.deadletter` (`deadletter_length` rose) | 0 |
| C4 | manual DLQ replay | VALIDATED | `/deadletter/replay` → `replayed=true` (exactly 1) | 0 |
| C5 | terminal failure | VALIDATED | `stream.deadletter.terminal` + sev2 incident + workflow `failed` | 0 |
| C6 | retry count limit | VALIDATED | dead-letter at `max_retries=3`, terminal at >3; loops settled | 0 |
| C-ui | DLQ operator visibility | **OPERATOR-FLAGGED UX GAP** | no dedicated DLQ / Retry Admin Console page (API-only) | 0 |

## Safety / no-production (across 65H)
| ID | Scenario | Result |
|---|---|---|
| D1 | production-effect / restricted action blocked | VALIDATED (A6; `waiting_approval`, not dispatched) |
| D3 | `production_executed_true_count` stays 0 | VALIDATED (before/after every scenario) |
| D4 | external write blocked when not authorized | VALIDATED (external flags stayed disabled throughout) |
| D5 | kill-switch effectiveness | VALIDATED (`hard_policy_enforced=true`; external all false) |

## This stage's posture
Documentation only. No new scenario executed; no external action; no production action.
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
