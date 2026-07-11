# Frontend Contract — 66C.3 Workroom Audit / Visibility / Edge-case Hardening

> **Retroactive contract.** Written after Step 66C.3 shipped (both backend and frontend implemented
> by Claude Code, before this collaboration-hub structure existed) to serve as the reference contract
> for that stage and the worked example for how future stages should populate
> `docs/contracts/<stage>/`. Source of truth for the actual behavior remains
> `docs/test/step66c3-workroom-audit-visibility-hardening-report.md` and the code itself
> (`apps/orchestrator/src/workroom_api.py`, `apps/admin-console/src/pages/TaskWorkroom.tsx`).

## Endpoints

### `GET /tasks/{task_id}/workroom`

- Required role: any of the six product RBAC roles that can view a workroom (Requester scoped to own
  task).
- Response now includes **server-side message visibility filtering** (G1) — the `messages` array
  only contains messages the caller's role is allowed to see (see
  `shared/sdk/tasks/workroom_rbac.py::_VISIBILITY_ROLES`). The frontend must not attempt to
  re-filter or add messages client-side.
- Safety fields: `dispatch_enabled: false`, `resume_dispatch_enabled: false` — always.

### `GET /tasks/{task_id}/audit-evidence`

- Required role: Platform Admin, Agent Operator, Security/Compliance Reviewer (read-only), or
  PM/Engineering Lead. Requester and Reviewer/Approver are denied by default
  (`403 role_cannot_view_audit_evidence`).
- Response: `{task_id, events: [<AuditEvidenceEntry>], dispatch_enabled: false,
  resume_dispatch_enabled: false}`.

## UI expectations

- A **visibility note** in the Workroom Messages section: "Some operator-only or audit-only messages
  may be hidden based on your role." — always shown, not conditional on role (the UI doesn't know in
  advance whether anything was actually filtered).
- An **Audit Evidence section** on the Workroom page:
  - On `403`, shows a readable restricted message ("Audit evidence is restricted for your current
    role.") — not a page-breaking error; the rest of the Workroom still renders.
  - On success, renders only the safe metadata fields (below) via plain React text interpolation.
- A readable error for `clarification_already_answered` (the G5 answered-twice guard) in the
  existing answer-form error slot.
- `dispatch_enabled: false` and `resume_dispatch_enabled: false` remain visible in the existing
  safety panel, unchanged.
- No raw message body or clarification answer is ever exposed through the Audit Evidence section.
- No production action anywhere in this contract's scope.

## `AuditEvidenceEntry` — allowed fields

```
audit_event_id
task_id
event_type
created_at
actor
role
action
status
message_id
clarification_id
message_type
visibility
body_length
body_hash
```

## Forbidden fields (must never appear in an `AuditEvidenceEntry` or anywhere in the Workroom API)

```
raw message body
raw clarification answer
headers
cookies
tokens
secrets
.env values
raw full payload
```

Backend enforcement is an **allowlist** (`_AUDIT_EVIDENCE_REF_FIELDS` in
`apps/orchestrator/src/workroom_api.py`), not a blocklist — any field not on the allowed-fields list
above is silently dropped, even if a future producer added one. Frontend enforcement is structural:
`AuditEvidenceEntry` (`workroomTypes.ts`) has no field for a raw body/answer, so there is no
rendering path that could display one even by accident.

## RBAC error mapping (frontend, `workroomClient.ts`)

| `detail` code | Readable message |
| --- | --- |
| `role_cannot_view_audit_evidence` | "Audit evidence is restricted for your current role." |
| `clarification_already_answered` | "This clarification has already been answered." |

## Statement

Contract specification only, describing already-shipped behavior. No runtime code change implied by
this document alone. No workflow dispatch. No workflow resume. No external action. No production
action. `production_executed_true_count=0`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
