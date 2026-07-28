# Step 66C.4-BE3-R2 — Resume Production-Effect Authoritative Closure Record

> **Remediation record only. Closes finding R2-1 (resume production-effect classification was
> client-controllable) noted as an observation during BE3-R1. No new BE3 capability, no
> architecture change, no frontend, no runtime activation, no deployment, no shared migration, no
> feature-gate enablement, no PR merge. Draft PR #20 remains Draft/OPEN/NOT FOR MERGE. This
> in-session remediation does not replace, weaken, or re-open the original combined independent
> BE3-R review's findings or verdict — its focused-closure gate remains the next required step.**

## Finding

```text
R2-1 — Resume production-effect classification is client-controllable.
```

Before this stage, `apps/orchestrator/src/operations_resume_api.py`'s `ResumeRequestCreate` accepted
a `production_effect: bool = False` field directly from the request body, and
`resume_service.request_resume` accepted it as a plain parameter and passed it straight through to
`authorization_service.request_authorization` — a client could set it to `false` regardless of the
owning task's real classification (or, before BE3-R1, achieve the same net effect against a task that
actually was production-effect). This is exactly the class of gap the binding security contract
forbids: production-effect classification must be server-derived from the authoritative owning
resource, and a client value must never be able to downgrade it.

## Preflight (§3)

1. **Authoritative task table/model:** `operator_tasks` (migration 029), read via
   `resume_request_repository.lock_task(conn, task_id)` (`SELECT * FROM operator_tasks WHERE
   id=$1 FOR UPDATE`) — the SAME row lock already taken for eligibility at every one of resume's
   three state-changing entry points.
2. **`production_effect` column type:** `BOOLEAN NOT NULL DEFAULT false` (migration 029) — never
   NULL, so there is no ambiguous "unset" state to reason about at the DB level.
3. **clarification → parent task:** `operator_clarification_requests.task_id UUID NOT NULL
   REFERENCES operator_tasks(id)` (migration 030) — a clarification always belongs to exactly one
   task; there is no client-supplied `task_id` anywhere in the resume request path (the API only
   ever accepts `clarification_id`), so the owning task is always resolved via this FK, never a
   client-chosen identifier.
4. **Task scope/ownership:** `operator_tasks.project_id` (nullable UUID, no FK — consistent with
   the same documented precedent already accepted for replay in the BE3-R review: "no team table
   upstream," project_id is the real authoritative isolation boundary). Cross-project resume
   requests were already masked as `not_found_masked` before this stage; unaffected, re-verified.
5. **Task state/version derivation:** previously
   `resource_state_version(clar) = f"{status}:{answer_ref}"` — did NOT include `production_effect`
   at all. Now `resource_state_version(clar, task) =
   f"{status}:{answer_ref}:{authoritative_production_effect(task)}"` (§9 option B: the
   classification is folded directly into the CAS predicate).
6. **Other resume entry points:** exactly three functions ever touch production-effect for
   resume — `request_resume`, `authorize_resume`, `prepare_execution` (all in
   `resume_service.py`) — all three now derive it from the SAME `operator_tasks.production_effect`
   column under the SAME task row lock via the ONE shared `authoritative_production_effect()` /
   `resource_state_version()` pair. No second source exists anywhere in the codebase.

## What changed

- **`shared/sdk/tasks/resume_request_model.py`:** new `authoritative_production_effect(task_row)`
  (fail-closed default `True` if the value were ever unresolvable, mirroring replay's existing
  convention); `resource_state_version` now takes `(clarification_row, task_row)` and folds the
  task's production-effect classification into the version string.
- **`shared/sdk/tasks/resume_service.py`:** `request_resume` no longer accepts a `production_effect`
  parameter at all (removed, not merely ignored) — it is computed via
  `model.authoritative_production_effect(task)` immediately after the task row is locked, and that
  value alone is passed to `authorization_service.request_authorization`. `authorize_resume` and
  `prepare_execution` (which already re-lock the clarification AND the task for eligibility)
  now recompute `resource_state_version(clar, task)` and compare it against the stored snapshot —
  unchanged control flow, only the version formula changed, so a task classification change
  between request/authorize/consume now correctly falls through the EXISTING `stale_state` path.
- **`apps/orchestrator/src/operations_resume_api.py`:** `production_effect` removed from
  `ResumeRequestCreate` entirely (the "Preferred" option) — Pydantic silently drops an unrecognized
  key from a client payload by default, so even a client that still sends the old field name has
  zero effect; the handler no longer reads or forwards it.
- **`authorization_service.consume` (Step 66C.4-BE3-R1):** unchanged and reused verbatim — since
  `production_effect` is now correctly set at request time from the authoritative source, the
  existing `production_action_approvals` resolution/consumption logic requires no modification to
  correctly enforce the approval gate for resume.
- **No migration was needed** — `resource_state_version` is a TEXT snapshot already recomputed
  fresh on every read; folding an additional fact into its formula required no schema change.

## Grant path confirmation (§11)

Re-confirmed, not re-implemented: `production_approval_service.grant_production_approval` /
`revoke_production_approval` remain **internal-service-only** — no HTTP router is registered
anywhere for them. RBAC is enforced via `production_approval_model.can_grant(actor.role)`, gated to
the canonical `{reviewer_approver, platform_admin}` pair; a Service Identity actor's role string
(`"agent_operator"`, `is_service_identity=True`) is not in that set, so it cannot grant regardless of
the identity flag; a plain Requester/Operator role likewise cannot. Grant/revoke audit evidence is
durable (`production_approval.granted` / `production_approval.revoked` bounded payloads via
`build_production_approval_audit_payload`). Status: **internal foundation only / no public grant
path / disabled** — unchanged from BE3-R1, no operator-facing grant UI or runtime activation added
in this stage.

## Scope discipline

Only the three files directly implicated were touched (model, service, API schema), plus the
required tests/verifier/records/gate/progress-log update. No migration was touched (none was
required). The BE3-R combined independent review's own findings (`be3-combined-independent-review.md`)
and verdict (`BE3_TECHNICAL_VERDICT: PASS`) are unmodified; this is a distinct, later, in-session
finding (R2-1), not a re-opening of that review.

## Status

```text
Step 66C.4-BE3-R2: IMPLEMENTED / SELF-VERIFIED / NOT MERGED / NOT DEPLOYED / NOT ACTIVATED
STEP66C4_BE3_R2_RESUME_PRODUCTION_EFFECT_VERIFY: PASS
Draft PR #20: Draft / OPEN / unmerged / untouched.
production_executed_true_count: 0.
```

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, usernames, or credentials appear in this record — only neutral labels._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
