# Step 66C.4-BE3-R1 — Required Findings Remediation Record

> **Remediation record only. Closes findings M-1 and L-1 recorded by the BE3-R combined independent
> review. No new BE3 capability, no frontend, no runtime activation, no deployment, no shared
> migration, no feature-gate enablement, no shared resume/replay execution, no destination-
> architecture change, no PR merge, no BE3-M. Draft PR #20 remains Draft/OPEN/NOT FOR MERGE.**

## Baseline

```text
Previous feature head: 6323972 (Step 66C.4-BE3-C)
Independent review branch: review/66c4-be3-combined-security-transaction @ 5626403
Findings being closed: M-1, L-1 (both Medium, both recorded as mandatory activation preconditions,
                        neither a merge blocker for the disabled foundation)
```

## Finding M-1 — Authoritative Production Approval Resolution

### Preflight (§3 of the original remediation prompt)

No existing table in this codebase models a production-effect approval bound to
team/project/resource/action for BE3 resume/replay (`human_approval_policies`/`human_approval_decisions`
target a different concern -- LLM proposal/auto-fix policy grants; `operator_action_requests` targets
Admin Console governed actions with no team/project columns; the "production approval channel
readiness model" is an explicit non-functional checklist that never grants approval). This was
recorded as an architecture blocker and referred to the Product Owner rather than faked shut — see
`be3-r1-m1-production-approval-contract.md` for the full investigation, the derivable design
decisions (cited from `docs/test/ai-team-work-rbac-blueprint.md` §3 and BE3-A precedent), and the
three genuine Product Owner decisions this required (binding granularity, validity bound,
state-version basis) with their answers (2026-07-28): **resource-scoped, single-use; same 1s-24h
bound as everywhere else in BE3; N/A (inherits the bound authorization's own resource_state_version
staleness protection)**.

### What was built

- **Authoritative source:** new table `production_action_approvals` (migration 035, additive; no
  column added to any existing table; no backfill).
- **Approval ID type:** canonical `UUID` (`approval_id`); `production_approval_reference` (still
  `TEXT` on `resume_replay_authorizations`, unchanged column type — no migration 032 edit was
  required) is parsed and validated as a UUID string by the resolver.
- **Valid states:** `granted` (the only state that can be consumed) / `revoked` / `consumed`. There
  is no separate pending/rejected state in this design — an approval is granted directly by an
  already-privileged Approver; "not granting one" is simply "no row exists."
- **Expiry/revocation semantics:** `expires_at` required, must be strictly after `granted_at`
  (`chk_paa_expiry_after_grant`); `revoked_at`/`revoked_by` CAS-guarded (`granted` + unconsumed only);
  an approval can never be both consumed and revoked (`chk_paa_not_consumed_and_revoked`) — the
  identical pattern as `resume_replay_authorizations` (BE3-A), reused, not reinvented.
- **Team/project/resource/action binding:** `team_id`/`project_id` `UUID NOT NULL`,
  `resource_type`/`resource_id`/`action_type` `NOT NULL`, resolved with exact equality against the
  SAME fields on the authorization being consumed.
- **Resource-state-version binding:** an independent snapshot (`resource_state_version TEXT NOT
  NULL`) taken at grant time, re-validated at resolve time — defense-in-depth alongside (not a
  replacement for) the bound authorization's own CAS version check.
- **Single-use consumption:** `resolve_and_consume_approval` (`production_approval_repository.py`)
  locks the approval row (`FOR UPDATE`) in the CALLER's transaction, validates every binding
  (existence, state, expiry, action, resource, scope, resource_state_version), and only then performs
  a guarded CAS `UPDATE ... SET state='consumed' ... WHERE state='granted' AND ... RETURNING *`.
  `consumed_by_authorization_id` carries a real FK to `resume_replay_authorizations(authorization_id)`
  — an approval's audit trail can never point at a fabricated authorization.
- **Transaction/lock model:** the resolver takes the CALLER's `asyncpg.Connection` and never opens
  its own connection or begins/commits/rolls back anything itself — the same composability
  requirement BE3-C already established for `replay_dead_row` vs. the connection-per-call
  `ClarificationOutboxRelay.replay_dead`. (`ApprovalPolicyStore`, the Stage-31 approval store, was
  explicitly NOT reused for this reason — it opens a fresh connection per call and cannot compose
  into a caller's transaction.)
- **Integration point:** `authorization_service.consume()` — the ONE shared function already called
  by both `resume_service.prepare_execution` and `replay_service.execute_authorized_replay` — now
  resolves and consumes the approval (when `production_effect` is true) BEFORE consuming the
  authorization itself. If approval resolution fails, the authorization is never consumed and no
  command/replay mutation ever occurs. If the approval consume SUCCEEDS but the authorization's own
  CAS then fails (a real, if narrow, possible race), the code raises to force a full transaction
  rollback rather than leave a consumed approval with an unconsumed authorization — the identical
  defensive pattern already used by `replay_service.execute_authorized_replay` for its own
  post-consume adapter-failure case.
- **RBAC:** grant/revoke are gated to the canonical `TASK_ROLES` {`reviewer_approver`,
  `platform_admin`} — the SAME pair as replay's Approver role, derived from the "Approve / reject
  gated action" row of `docs/test/ai-team-work-rbac-blueprint.md` §3 (no second RBAC system).
- **Fail-closed behavior:** missing / unparsable / unknown / revoked / expired / already-consumed /
  wrong-action / wrong-resource / wrong-scope / stale-version references are ALL rejected, mapped to
  distinct `production_approval_*` reason codes (added to the bounded `authorization_model.
  REASON_CODES` allowlist) that all resolve to the SAME `result_kind` (`production_approval_required`,
  HTTP 409) so the API-level status mapping is unchanged.
- **No new HTTP surface in this stage:** grant/revoke are internal-only service functions
  (`production_approval_service.py`); no router is registered. A future, separately-authorized stage
  may add an operator-facing grant/revoke API.
- **A pre-existing gap NOT in scope, noted for visibility:** for RESUME (unlike replay), the
  `production_effect` FLAG ITSELF is still client-supplied (`ResumeRequestCreate.production_effect`
  in the request body) rather than server-derived from the owning task, unlike replay (which the
  BE3-R review already confirmed derives it server-side). This was not flagged as a finding by the
  BE3-R review and is outside the explicit M-1/L-1 remediation scope authorized for this stage; it
  does not weaken M-1's own closure (the approval REFERENCE is now always genuinely resolved
  regardless of how `production_effect` was set), but is recorded here so it is not silently lost.

## Finding L-1 — Concurrency-Safe Per-Actor Replay Rate Limit

- **Serialization mechanism:** a PostgreSQL transaction-scoped advisory lock
  (`pg_advisory_xact_lock(hashtextextended(key, 0))`, key = `team_id:project_id:actor_id`), acquired
  in `replay_service.request_replay` BEFORE any row lock (consistent lock-acquisition order across
  every call path, avoiding deadlock), auto-released at the caller's transaction commit/rollback. A
  hash collision between two DIFFERENT keys can only cause extra, harmless serialization — the actual
  COUNT query remains exactly scoped, so it can never loosen or merge two different keys' caps.
- **Scope isolation (closed a related, previously-unflagged gap):** `count_recent_requests_by_actor`
  was previously a GLOBAL per-actor count with no team/project filter at all. It is now scoped by
  `(team_id, project_id, requested_by)`, so cross-team/cross-project actor statistics are isolated —
  required by L-1's own "同一actor不同team/project: isolated limits" test.
  `idx_rpr_scope_actor_requested_at` (migration 034, still unapplied anywhere — edited in place, not
  a new migration) supports the scoped query.
- **Rolling-window semantics:** unchanged — PostgreSQL `statement_timestamp()` authoritative;
  configurable window (default 24h), bounded and fail-closed on invalid config (unchanged from BE3-C).
- **Idempotency handling:** unaffected by the lock change — the pre-existing
  `uq_rpr_idempotency_key` UNIQUE constraint already guarantees a retried request with the same key
  can never create a second row, so it was already impossible to double-count (verified with a new
  concurrent-retry test).
- **Counting policy (documented, unchanged):** every CREATED request counts against the actor cap
  regardless of its later state (executed/canceled/rejected/expired all count) — the cap defends
  against request STORMS, not just successful replays; the per-event successful-replay hard cap (3/
  24h default) is unaffected and remains index-serialized-safe as the BE3-R review already confirmed.
- **No bypass:** no role (including `platform_admin`) is exempted from the cap at any layer.

## Scope discipline

Only the files listed as directly required were touched: `authorization_service.py`,
`authorization_model.py` (new reason codes), `replay_service.py` / `replay_request_repository.py`
(the lock + scoped count), migration 034 (one supporting index, in place, still unapplied), a NEW
migration 035 + the three new `production_approval_*` modules (explicitly authorized by the operator
as the M-1 closure design), direct tests/verifier, and this record set. No feature gate was added or
enabled; no shared migration was applied; no runtime was activated; no PR was merged.

## Status

```text
Step 66C.4-BE3-R1: IMPLEMENTED / SELF-VERIFIED / NOT MERGED / NOT DEPLOYED / NOT ACTIVATED
STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY: PASS
Draft PR #20: Draft / OPEN / unmerged / untouched.
production_executed_true_count: 0.
```

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, usernames, or credentials appear in this record — only neutral labels
("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
