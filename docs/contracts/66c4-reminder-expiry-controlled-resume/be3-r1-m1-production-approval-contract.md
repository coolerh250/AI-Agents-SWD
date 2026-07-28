# Step 66C.4-BE3-R1-M1-P — Production-Action Approval Registry: Planning Checkpoint

> **Planning/contract document only. No backend/API/migration/frontend/deployment code in this
> checkpoint. No runtime change, no external action, no production action. Records what is
> DERIVABLE from canonical governance documents (with citation) and what is a genuine, undecided
> Product Owner decision, per the operator's explicit instruction not to invent the production-
> approval business process while coding.**

## 1. Why this checkpoint exists

Step 66C.4-BE3-R (combined independent review) recorded finding **M-1**: `resume_replay_authorizations.production_approval_reference`
is checked only for non-emptiness at consume time, never resolved to a real production approval.
Closing M-1 requires an authoritative approval registry. Preflight investigation (Step 66C.4-BE3-R1,
this stage) established that **no existing table in this codebase models a production-effect
approval bound to team/project/resource/action for BE3 resume/replay**:

- `human_approval_policies` / `human_approval_decisions` (Stage 31, migration 011) are scoped to
  `task_id`/`workflow_id`/`allowed_actions` for a *different* concern — LLM proposal / auto-fix
  policy grants during software delivery. No notion of "production effect"; `allowed_actions` does
  not include `resume`/`replay`.
- `operator_action_requests` / `operator_action_confirmations` (migration 023, Admin Console) target
  `target_type`/`target_id` governed actions and have no team/project columns at all.
- `docs/operations/production-approval-channel-readiness-model.md` (Step 63A) is a **readiness
  checklist only** — it explicitly states `approval_granted: false` always, and sends no real
  notification. It is not, and was never meant to be, an approval registry.
- `be3-operator-resume-replay-authorization-contract.md` §4 (D5) recommends "Operator request +
  separate production approval + policy authorization... **unchanged from the existing
  production-effect gate**" — but no such gate has ever been implemented; every BE3-A/B/C record
  states production approval is validated only as a non-empty reference (this is exactly M-1).

Per the operator's decision (2026-07-28): build a **new, dedicated, generic production-action
approval registry** in this same BE3-R1 flow, but only after this planning checkpoint records the
binding contract, and only using decisions that are actually derivable from canonical governance —
stopping to ask the Product Owner for anything that is not.

## 2. What IS derivable from canonical governance (cited)

### 2.1 Authoritative registry
A **new** additive table, `production_action_approvals` (working name), purpose-built for this
concern. Decided by explicit operator instruction (not re-litigated here).

### 2.2 Approver roles
`reviewer_approver` and `platform_admin` — derived from the canonical MVP role→capability matrix,
`docs/test/ai-team-work-rbac-blueprint.md` §3, row **"Approve / reject gated action"**:
`Requester ✖ · PM/Eng Lead ✖ · Reviewer/Approver ✔ · Platform Admin ✔ · Agent Operator ✖ ·
Sec/Compliance ✖`. This is the SAME role pair already implemented (and BE3-R-reviewed as SOUND) as
replay's `_REPLAY_APPROVER_ROLES` in `authorization_policy.py`. No new role, no second RBAC system —
reuses the canonical six-role `TASK_ROLES` vocabulary verbatim, consistent with the standing "no
second parallel RBAC" constraint (`be3-operator-resume-replay-authorization-contract.md` §5).

### 2.3 Team / project / resource / action binding
Mirrors `resume_replay_authorizations` (migration 032) exactly: `team_id UUID NOT NULL`,
`project_id UUID NOT NULL`, `resource_type TEXT NOT NULL`, `resource_id UUID NOT NULL`,
`action_type TEXT NOT NULL` (`'resume' | 'replay'`), scope predicate `IS NOT DISTINCT FROM` (exact
null-safe equality, NULL never a wildcard) — the identical pattern already independently reviewed as
SOUND for scope isolation in the BE3-R combined review §B. This is explicit in the M-1 finding text
itself ("approval belongs to same team_id / project_id / resource / action").

### 2.4 Revocation semantics
CAS `authorized/granted -> revoked`, guarded by `consumed_at IS NULL` (a consumed approval can never
be revoked; a revoked approval can never be consumed) — the identical pattern already implemented
and BE3-R-reviewed as SOUND in `resume_replay_authorizations` (`chk_rra_not_consumed_and_revoked`,
`repo.revoke`). Reused verbatim, not reinvented.

### 2.5 Transaction and locking model
`SELECT ... FOR UPDATE` row lock taken by the CALLER's transaction (never a separate connection, per
M-1 §3 Q6: "能否在authorization consume的同一PostgreSQL transaction中鎖讀") — the identical pattern
used by `authorization_repository.py`, `resume_request_repository.py`, and
`replay_request_repository.replay_dead_row`. The resolver is a NEW, transaction-aware repository
function (never the connection-per-call `ApprovalPolicyStore` pattern, which cannot compose into a
caller's transaction — the same composability problem BE3-C already solved for
`ClarificationOutboxRelay.replay_dead` vs. the new `replay_dead_row`).

### 2.6 Audit evidence
Bounded, secret-free, positive-allowlist payload (`event`, `approval_id`, `action_type`,
`resource_type`, `resource_id`, `team_id`, `project_id`, `actor_id`, `state`, `reason_code`,
`occurred_at`) — the identical pattern as `authorization_model.build_audit_payload` /
`replay_request_model.build_replay_audit_payload`. Approval **decision content/rationale is never
stored in audit** — only the approval id, its resolved state, and a bounded reason code (per M-1 §6:
"不得記approval內容、token或credential").

### 2.7 Reference type
`production_approval_reference` (currently `TEXT`, migration 032) is treated as a canonical
`approval_id` (`UUID`). If the column type needs tightening this is a minimal, in-place edit to the
still-unapplied migration 032 (permitted by the R1 scope: "migration 032/034 if directly required and
still unapplied"), not a new migration.

### 2.8 Stage boundary (this stage builds NO new HTTP surface)
Per the operator's explicit instruction ("The new foundation must remain disabled and undeployed. No
shared migration, runtime activation, production action, or PR merge is authorized") and the original
BE3-R1 prompt's forbidden list ("不得...新增BE3能力"), this stage adds the table + a transaction-aware
repository/resolver + tests only — **no public grant/revoke HTTP endpoint**. Tests and the resolver's
own test fixtures create approval rows directly via the repository, exactly as every other BE3 test
file creates authorizations/requests directly via repository/service calls today. A future,
separately-authorized stage would build any operator-facing grant/revoke API.

## 3. What is NOT derivable — genuine Product Owner decisions required

The following are NOT answered by any canonical document found in this codebase (searched: all
`docs/contracts/66c4-reminder-expiry-controlled-resume/*`, `docs/operations/production-*.md`,
`docs/test/ai-team-work-rbac-blueprint.md`, migrations 011/023/029-034). Per the operator's
instruction, implementation of the registry/resolver STOPS here pending these decisions:

**Q1 — Binding granularity and reusability.** Is a production approval scoped to the SPECIFIC
resume/replay resource (`resource_type`/`resource_id` = the same `clarification_id` /
`outbox_event_id` that `resume_replay_authorizations` uses — one approval, single-use, consumed
alongside that one authorization), or to the owning TASK (`resource_type='task'`,
`resource_id=task_id` — one sign-off reusable by multiple resume/replay attempts on that task within
its validity window)? `operator_tasks.production_effect` is itself a task-level flag, and D5's own
text ("unchanged from the existing production-effect gate") suggests a task-level concept, but this
is not stated explicitly anywhere, and the M-1 finding's own wording ("approval belongs to same...
resource") is compatible with either reading.

**Q2 — Validity duration bound.** `resume_replay_authorizations.expires_at` is caller-supplied,
API-bounded to 1 second–24 hours (`expires_in_seconds`, `ge=1, le=86400`) everywhere else in BE3. A
production approval is a less frequent, higher-stakes grant — should it reuse the same conservative
1s–24h bound, allow a longer bound (e.g. days), or have no expiry (revoke-only)? No canonical default
exists for this specific gate.

**Q3 — Resource-state-version binding basis.** M-1 §4 requires "approval resource state/version is
still applicable." Clarifications already have a computed `resource_state_version` (`model.
resource_state_version(clar)`); `operator_tasks` has no equivalent column or derivation today. If Q1
resolves to task-level binding, what should the approval's resource-state-version be derived from —
the task's own `(status, updated_at)` composite (mirroring the clarification pattern), no
state-version check at all for a task-level approval, or something else?

No further implementation (table, migration edit, repository, resolver, tests) proceeds until these
are answered.

## 4. Status

```text
Step 66C.4-BE3-R1-M1-P: PLANNING CHECKPOINT ONLY / NOT IMPLEMENTED / NOT MERGED / NOT DEPLOYED
L-1 (separately): implemented this same session, pending final PostgreSQL verification.
```

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, real tokens, credentials, private URLs, or environment secrets._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
