# Product Microcopy Guide — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. Concrete before/after microcopy, tone rules, and a reusable string set.
> Product language, active voice, consequence-explicit. UI strings are English (matching the app);
> this guide is the source of truth for later phases too.

## Tone rules

1. **Name things by what a person does, not how the system is built.** "Automated actions: off," not
   `dispatch_enabled: false`.
2. **Active voice, consequence-explicit.** A control says what will happen; a toast confirms it
   happened ("Answer" → "Answer recorded").
3. **Reassurance-first for safety.** Safe/off states are good news, phrased calmly and positively.
4. **Errors: what happened + what to do.** No bare codes, no apologies, no vagueness.
5. **No raw field names, no `snake_case`, no internal identifiers** in primary copy.

## Safety & governance strings (before → after)

| Before (deployed) | After (product) |
| --- | --- |
| `production_executed_true_count: 0` | No production actions have run. |
| `dispatch_enabled: false` | Automated actions: Off. |
| `resume_dispatch_enabled: false` | (folds into) Automated actions: Off. |
| `github_external_write_enabled: false` etc. | External integrations: Off. |
| `approval_required: true` | Needs approval before anything runs. |
| `requires_approval: false` | No approval needed for this. |
| (safety bar overall) | Safe — no automated or production actions will run. Everything is recorded. |
| `production_effect = true` warn-banner (jargon) | This task may affect production. It will pause for approval and will not run automatically. No production action occurs. |

## Task strings

| Before | After |
| --- | --- |
| "Operator task assignment (Step 66B). No workflow dispatch occurs from this page." | "Assign work to the AI team. Nothing runs automatically — you stay in control." |
| Column `Production effect` (always shown) | "May affect production" — shown only when true. |
| Column `Requires approval` (always shown) | "Needs approval" — shown only when true. |
| Raw `created_at` / `updated_at` | "Created 2 days ago" / "Updated 2 hours ago" (exact on hover). |
| "Task Detail" (+ raw KeyValueTable) | "<Task title>" as a header with stage, owner, and what's next. |

## Workroom & clarification strings (later phases; defined now)

| Before | After |
| --- | --- |
| `message_type: clarification_question` card | "The Requirement Agent needs your decision to continue." |
| "Create Clarification" / "Use this when a required human answer is needed…" | keep intent; frame as "Ask the AI team for a decision" vs. "Send a message" (general discussion). |
| "Answer Clarification" | "Answer" → confirm toast "Answer recorded." |
| metadata line `sender_type · sender_id · sender_role · created_at` | "Requirement Agent · 2 hours ago" (technical detail on hover). |
| Resume-disabled note | "Answering won't automatically restart the AI team. A person still decides the next step." |

## Overview / dashboard strings

| Tile | Copy | Placeholder (if gated) |
| --- | --- | --- |
| Decisions waiting | "N agents waiting on your answer" | — |
| Deliveries to review | "N ready for your acceptance" | "Requires Step 66D" (show "—", not a number) |
| Blocked tasks | "N waiting on an input" | — |
| Approvals | "N need approval" | "Requires Step 66D" |
| Safety card | "All systems safe — nothing runs automatically." | — |

## Empty / loading / error strings

| State | Copy |
| --- | --- |
| Tasks empty | "No tasks yet. Assign your first piece of work to the AI team." |
| Workroom empty | "No messages yet. Start a discussion or ask the AI team a question." |
| Clarifications empty | "No open decisions. The AI team doesn't need your input right now." |
| Deliveries placeholder | "Not yet available. Requires Step 66D. No workflow action available." (unchanged safety text) |
| RBAC denied | "Your current role can't do this. Switch role in test mode or ask your platform admin." |
| Load error | "Couldn't load this. Retry, or check system status." |
| Loading | skeletons; no bare "Loading…" where a skeleton fits. |

## Reserved / do-not-use in primary copy

`dispatch`, `resume`, `production_executed_true_count`, `snake_case` field names, correlation/audit
IDs, hashes — all allowed only inside a "Technical details" disclosure, never as the headline.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
