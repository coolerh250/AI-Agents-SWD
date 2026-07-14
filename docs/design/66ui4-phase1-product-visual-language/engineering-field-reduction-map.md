# Engineering-Field Reduction Map — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. A concrete, field-by-field map from the raw backend names currently shown in
> the deployed UI to product language, with a disposition for each: **relabel**, **demote**
> (move to expandable detail / hover), or **hide** (not user-facing). Grounded in the actual
> deployed components.

## Principle

The primary layer speaks product language. Technical field names remain **available** (hover /
expand / a "technical details" disclosure) for engineers, but are never the headline. Nothing here
changes a value or its server provenance — only how it is labeled and where it appears.

## SafetyStatusBar fields (`SafetyStatusBar.tsx` — highest priority)

| Raw field (shown today) | Disposition | Product language |
| --- | --- | --- |
| `production_executed_true_count` | relabel (summary) | "Production actions: None run" (when 0) |
| `workflow_production_executed_true_count` | demote | folds into "Production actions"; exact field on expand |
| `dispatch_enabled` | relabel | "Automated actions: Off" |
| `resume_dispatch_enabled` | relabel | folds into "Automated actions: Off" |
| `task_api_workflow_dispatch_enabled` | demote | technical detail under "Automated actions" |
| `task_workroom_resume_dispatch_enabled` | demote | technical detail under "Automated actions" |
| `github_external_write_enabled` | relabel/group | "External integrations: Off" (GitHub) |
| `discord_external_send_enabled` | relabel/group | "External integrations: Off" (Discord) |
| `llm_external_call_enabled` | relabel/group | "External integrations: Off" (LLM) |
| `production_delegation_allowed` | demote | technical detail under "Production actions" |
| `approval_required` | relabel | "Approvals: required / not required" |
| `requires_approval` | relabel | folds into "Approvals" |

Result: 12 raw fields → 5 human rows (Automated actions / Production actions / External integrations
/ Approvals / Audit), each expandable to its exact backing field(s). See
`calm-safety-posture-spec.md`.

## Task Detail (`TaskDetail.tsx` — `KeyValueTable` raw object dump + safety panel)

| Raw field | Disposition | Product language |
| --- | --- | --- |
| whole task object via `KeyValueTable` | **replace** | a task header (title, stage, owner, what's next) — retire the raw dump; full field table available under a "Technical details" disclosure |
| `production_effect` | relabel | "May affect production" (with plain explanation of what will/won't happen) |
| `requires_approval` | relabel | "Needs approval before anything runs" |
| `dispatch_enabled` | relabel | "Automated actions: Off" (reuse posture component) |
| `external_actions_enabled` | relabel | "External integrations: Off" |
| `production_executed` | relabel | "No production actions have run" |
| `environment` | relabel | "Environment: <value>" (keep, it's meaningful; not jargon) |
| `created_at` / `updated_at` | relabel | relative time ("2 hours ago"), exact on hover |

> Note: Task Detail's full redesign is a later phase (Direction B). Phase 1 defines these mappings so
> the later work is consistent; Phase 1 itself only needs to apply the global posture component and
> microcopy where Task Detail already shows safety fields.

## Task List (`TaskList.tsx` — later phase; mapping defined now)

| Raw column | Disposition | Product language |
| --- | --- | --- |
| `task_type` | relabel | "Type" with friendly labels (already partly done via `TASK_TYPE_OPTIONS`) |
| `production_effect` (badge) | relabel | "May affect production" chip only when true; nothing when false (don't show a red/neutral chip for the common safe case) |
| `requires_approval` (badge) | relabel | "Needs approval" chip only when true |
| `created_at` / `updated_at` | relabel | relative time; raw on hover |
| (missing) "waiting on you" | **add** | a triage signal column/sort (later phase) |

## Workroom (`TaskWorkroom.tsx` — later phase; mapping defined now)

| Raw metadata (shown today) | Disposition | Product language |
| --- | --- | --- |
| `message_type` | demote | conveyed by message *treatment*, not a printed type string |
| `sender_type` | hide | implied by treatment (human vs agent) |
| `sender_id` (e.g. "Requirement Agent") | relabel | agent identity chip (name + monogram) for agents; display name for humans |
| `sender_role` | demote | on hover / expand |
| `created_at` | relabel | relative time; exact on hover |
| `correlation_id` / `audit_ref` | demote | technical detail, expandable |
| `visibility` | demote | a small "role-limited" marker only when relevant |

## Audit Evidence (later phase; mapping defined now)

| Raw field | Disposition | Product language |
| --- | --- | --- |
| `event_type` | relabel | human sentence ("Requirement Agent requested a clarification") |
| `actor` / `role` | relabel | actor name + role, plainly |
| `body_length` / `body_hash` | demote | secondary "integrity detail," expandable — not the headline |
| `correlation_id` / `message_id` / `clarification_id` | demote | technical detail, expandable |
| `created_at` | relabel | relative time; exact on hover |

(Raw message/answer **bodies** remain never-shown — unchanged rule.)

## Rule for Codex (when later authorized)

- Relabel/demote/hide is **presentation only**; the value and its server source are unchanged.
- A "Technical details" disclosure may expose exact field names for engineers — available, not
  foregrounded.
- Never hide a **safety-relevant** signal; only relocate its technical representation while keeping
  the plain-language statement visible.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
