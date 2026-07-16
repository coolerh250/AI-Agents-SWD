# Existing Data Mapping — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. The honesty backbone: every Overview element mapped to an **existing** data
> source, or explicitly marked **Future — requires later contract**. No new backend endpoint, DB
> field, or computation is requested.

## Existing sources the frontend can already use

| Source | Call | Already used by |
| --- | --- | --- |
| Overview aggregate | `GET /operations/admin-console/overview` (`getOverview`) | `ExecutiveOverview.tsx` |
| Tasks list | `GET /tasks` (`taskApi.list`) | `TaskList.tsx` |
| Safety posture | `GET /operations/safety` (`getSafety`) | FE.1B safety posture component |
| Agent executions | `GET /operations/agent-executions` (`getAgentExecutions`) | Agent Executions page |

## Section-by-section mapping

### B. Needs your attention

| Item | Source | How | Honesty |
| --- | --- | --- | --- |
| Decisions waiting | `GET /tasks` | client-side count of tasks with status `clarification_needed` | existing data; count computed client-side from existing list, **no new endpoint** |
| Blocked tasks | `GET /tasks` | client-side count of tasks with status `blocked` | existing data; client-side count |
| Deliveries to review | — | **Future — requires 66D** | honest placeholder; do NOT use the legacy `ready_for_review_packages_count` here |
| Approvals queue | — | **Future — requires 66D** | honest placeholder (task `requires_approval` flags may inform a per-task badge in section D, but the Approval *queue/action* is 66D) |

> Note: using `GET /tasks` on the Overview is a **new call site of an existing endpoint**, not a new
> endpoint. Flagged for Claude Code confirmation in `open-questions-and-risks.md`. If Claude Code /
> Product Owner prefer the Overview not call the tasks list, the attention counts fall back to the
> honest empty state — the design degrades safely.

### C. AI team activity

| Item | Source | How | Honesty |
| --- | --- | --- | --- |
| Recent agent runs | `GET /operations/agent-executions` | list recent executions as product-readable status (agent name + state + relative time) | existing data; presentation only. Empty → "No recent agent runs." |

### D. Current work snapshot

| Item | Source | How | Honesty |
| --- | --- | --- | --- |
| Recently updated tasks | `GET /tasks` | top N by `updated_at`; show title + product-readable status + relative time; link to task | existing data |
| Per-task flags (optional) | `GET /tasks` | `production_effect` / `requires_approval` shown as a chip only when true | existing fields |

### E. System posture

| Item | Source | How | Honesty |
| --- | --- | --- | --- |
| Calm posture summary | FE.1B component (backed by `GET /operations/safety`) | **reuse FE.1B output**; one line + link to Safety Center | existing; must NOT duplicate/re-fetch FE.1B detail |
| Safety / production summary | `GET /operations/admin-console/overview` (`safety_result`, `production_executed_true_count`) | optional one-line reassurance if FE.1B summary not directly embeddable | existing fields |

### F. Platform & delivery metrics (demoted — the existing 12 cards)

All from `getOverview()` (existing), moved to a secondary section, unchanged data:

```text
active_projects_count · delivery_packages_count · ready_for_review_packages_count ·
latest_mini_delivery_pilot_status · latest_delivery_package_status ·
latest_acceptance_gate_decision · latest_human_acceptance_status · safety_result ·
production_executed_true_count · latest_full_regression_status ·
delivery_package_ready_for_admin_console · backup_readiness_gaps
```

### G. Future capabilities (placeholders only — no data)

| Item | Gate |
| --- | --- |
| Delivery Review | Future — requires Step 66D |
| Reminder / Expiry | Future — requires Step 66C.4 |
| Notifications / Action Center | Future |
| Pipeline view | Future (read-only only; no drag/drop) |

## Explicitly excluded (NOT requested by FE.1C)

```text
- new backend metrics endpoint
- new database fields
- new workflow state computation
- new agent activity stream
- new notification service
- new delivery review backend
- new reminder/expiry scheduler
```

Any element above that would need one of these is labelled **Future — requires later contract** and
is out of FE.1C implementation scope.

## Statement

Design specification only. No runtime code. No production action. No new backend/API/DB/workflow
requested.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
