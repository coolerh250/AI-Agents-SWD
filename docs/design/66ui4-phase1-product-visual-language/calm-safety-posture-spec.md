# Calm Safety Posture Spec — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. Replaces the raw-field `SafetyStatusBar` with a calm, plain-language posture
> indicator. **Same server values, product presentation.** Values stay server-computed and
> displayed-as-returned — never hardcoded or inferred client-side.

## Problem (deployed today)

`SafetyStatusBar.tsx` prints 12 verbatim backend fields as a flat grey run:
`production_executed_true_count`, `workflow_production_executed_true_count`, `dispatch_enabled`,
`resume_dispatch_enabled`, `task_api_workflow_dispatch_enabled`,
`task_workroom_resume_dispatch_enabled`, `github_external_write_enabled`,
`discord_external_send_enabled`, `llm_external_call_enabled`, `production_delegation_allowed`,
`approval_required`, `requires_approval`. It reads as a debug panel on every page and is the single
most pervasive engineering signal.

## Design: a calm posture summary + expandable detail

### Collapsed (default, on every page)

A single calm line, reassurance-first, in the top bar:

```text
🛡  Safe — no automated or production actions will run.   Details ▾
```

- When everything is in its safe/default state (the current reality: all dispatch/resume off,
  `production_executed_true_count = 0`, no external actions enabled), show the calm/positive
  treatment above — **an off safety flag is good news and must not read as a red alarm.**
- The indicator is **derived from the same server fields**, mapped to one summary state. The mapping
  is presentation-only; the underlying values are still fetched from `/operations/safety` (or the
  existing source `SafetyStatusBar` already uses) and shown as returned on expand.

### Summary-state logic (presentation mapping only)

| Summary shown | When (from server values) | Treatment |
| --- | --- | --- |
| "Safe — no automated or production actions will run." | dispatch/resume all false AND production_executed_true_count = 0 AND no external action enabled | calm / positive |
| "Attention needed — items awaiting approval." | approval_required / requires_approval true (server) | amber |
| "Posture unavailable." | safety endpoint error (existing error branch) | neutral, not alarming |

No client-side inference of the *values* — only which plain-language summary to show given the
values the server returns. If a value is missing, show "not reported" (as today), never a guessed
default.

### Expanded (Details ▾)

Grouped, human-labeled, with the raw field name available as secondary caption/hover for engineers:

```text
Automated actions            Off        (dispatch_enabled, resume_dispatch_enabled … all false)
Production actions           None run   (production_executed_true_count = 0)
External integrations        Off        (GitHub / Discord / LLM sending: not enabled)
Approvals                    Not required for current context
Audit                        All actions recorded
```

Each human row can reveal its exact backing field(s) on hover/expand for technical users — the
engineering detail is *available*, not *foregrounded*.

## States to preserve (unchanged semantics)

- `dispatch_enabled=false` / `resume_dispatch_enabled=false` → "Automated actions: Off".
- `production_executed_true_count=0` → "Production actions: None run."
- external-action-disabled → "External integrations: Off."
- approval-required → amber "Attention needed" summary + row.
- RBAC-denied (on any page) → readable message, unchanged.
- audit-restricted → readable restricted message, unchanged.

## Placement

- Global: the calm collapsed line lives in the persistent top bar (replaces the current
  `.safety-status-bar` content, same location).
- Task-scoped (Direction B, later phases): a compact task posture chip inside the Workroom/Task
  workspace reuses this same component/logic.

## Hard rules

- Server-computed, displayed-as-returned; **no hardcoding, no client-side inference of values.**
- No control in this indicator implies enabling dispatch/resume/production/external action.
- Never present an *off* safety flag as danger-red; reassurance-first.
- Simplification relocates detail (to expand/hover); it must never *remove* a safety signal.

## Accessibility

- Summary state carried by text + icon, not color alone.
- Expand control keyboard-focusable; expanded detail is a proper disclosure.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
