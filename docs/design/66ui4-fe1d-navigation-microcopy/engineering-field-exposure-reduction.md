# Engineering-Field Exposure Reduction — Step 66UI.4-FE.1D

> Owner: Claude Design. Categorizes engineering-flavored fields by what FE.1D (frontend-only) may do
> with each. Grounded in the deployed source.

## Categories (per stage prompt §4.3)

- **A** — FE.1D can relabel to a product label (display string only).
- **B** — FE.1D can move to a "Technical details" disclosure / raw-evidence section on a page that
  already renders the field.
- **C** — FE.1D should NOT touch; reserved for a later feature-design phase.
- **D** — cannot be done frontend-only; needs backend / API / data-model support (out of FE.1D).

## Field categorization

| Field / label | Category | Rationale / action |
| --- | --- | --- |
| `production_executed_true_count` ("Production executed" in Overview metrics) | A | relabel "Production actions" (align FE.1B.1). Safety-panel copy already handled. |
| `dispatch_enabled`, `resume_dispatch_enabled` | A (already done) | FE.1B.1 already shows "Workflow dispatch"/"Workflow resume". Leave — no re-rename. |
| `task_api_workflow_dispatch_enabled`, `task_workroom_resume_dispatch_enabled` | B (already done) | already inside CalmSafetyPosture evidence disclosure. Leave. |
| `audit_integrity` / hash fields (`body_hash`, `payload_hash`, `metadata_hash`) | B | keep in evidence disclosure; relabel "…hash" → "Integrity check" [confirm]. Never surface raw hash as a headline. |
| `created_at` / `updated_at` raw ISO | A | show relative time, exact on hover (TaskList; Overview already does this). |
| Task `status` / `task_type` raw enums | A | product labels via shared maps; enum value unchanged. |
| `production_effect`, `requires_approval` booleans | A | "May affect production" / "Needs approval" chips only when true. |
| raw `task_id` / `work_item_id` / `execution_id` / `event_id` shown as text | B | move under "Technical details" where a page renders them raw (Audit / Evidence / Operator). [confirm which pages] |
| `correlation_id`, `message_id`, `clarification_id` | B | move under "Technical details" (Audit Evidence); human event line stays primary. |
| `workflow_id` | C | reserved — appears in workflow/graph contexts tied to future workflow features; don't relabel piecemeal now. |
| HTTP-like / endpoint labels ("Endpoint result", "Not applicable at this endpoint") | A (already done) | FE.1B.1 wording is acceptable; leave. |
| `deadletter` / DLQ terminology | A (nav subtitle) | Operator Center nav subtitle "Needs recovery"; keep route. |
| UUIDs shown as primary identifiers on operational rows | B or D | if the UI *can* show a human title instead of the UUID from existing data → B; if only the UUID exists in the payload → **D** (needs backend to return a human label). [confirm with Claude Code per page] |
| Any field requiring a NEW value the backend doesn't return (e.g. human-readable agent name where only an id exists) | D | out of FE.1D; note as "未來才做 — needs backend/API". |

## Decision rule for Codex

1. If a friendlier value is **already in the existing payload** → category A/B, FE.1D-eligible.
2. If it requires a value the backend does **not** currently return → category **D**, out of scope;
   record as a future backend suggestion, do not fake it.
3. Never remove a **safety-relevant** signal — relocation of technical detail only, keeping the
   plain-language statement visible (safety substance already handled by FE.1B/FE.1B.1).

## Explicitly out of FE.1D

- Task Detail's full redesign (Direction B, later phase). FE.1D may only (a) relabel its safety
  panel fields to the shipped product labels and (b) wrap its raw `KeyValueTable` object dump in a
  "Technical details" disclosure (category B, frontend-only) — **[confirm scope with Claude Code]**;
  it must not restructure the page.
- Anything category C or D.
- The SPA deep-link fallback (backend; see design-brief).

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
