# Step 66C.4-BE3-R — Combined Independent Security / Authorization / Transaction Review

> **Independent review document only. Reviews CODE MERGE READINESS of BE3-A + BE3-B + BE3-C as one
> combined foundation. Authorizes NO merge, NO deployment, NO shared-migration application, NO
> producer cutover, NO gate activation. `production_executed_true_count` remains 0.**

## Scope and independence

- Reviewed baseline (canonical main): `5745ab7`
- Reviewed feature head: `6323972` (feature branch `feature/66c4-be3-resume-replay-authorization`)
- Review diff: `5745ab7..6323972`
- Review branch: `review/66c4-be3-combined-security-transaction` (adds review docs + independent
  verifier + independent tests + this record only; touches NO implementation file)
- Draft PR #20: remained Draft / OPEN / unmerged throughout; not touched by this review.

Every conclusion below was re-derived from the committed code, migrations, and contracts and
re-tested against an isolated ephemeral PostgreSQL 16 (and an isolated ephemeral Redis 7 for the
relay routing test) by an independent verifier + independent test suite written for this review. No
implementation self-verifier or implementation record was accepted as sufficient evidence on its
own; the dead-episode version claim in particular was independently re-derived (Section H).

## Technical verdict

```
BE3_TECHNICAL_VERDICT: PASS
```

PASS is for **code merge readiness of a disabled-by-default foundation only**. No
Critical/High finding. Every enumerated no-compromise property (authorization single-use/CAS,
scope isolation, Policy-Authority unforgeability, resume transactions, command routing, replay
two-person control, transaction/rollback completeness, dead-episode state-version determinism,
production-approval non-bypass at the system level, feature-gate no-side-effect) is sound and was
verified under real concurrency. Two Medium findings (M-1, L-1) are recorded as **mandatory
activation preconditions** — they do not compromise the disabled foundation and no production
effect is reachable, but they MUST be closed before the corresponding runtime activation.

---

## A. Authorization model (migration 032 + authorization_service/repository/policy) — SOUND

- Resource-, action-, team-, project-bound; single-use (`consumed_at`), time-bounded
  (`expires_at`), state-version-bound (`resource_state_version`), revocable-before-consume
  (`revoked_at`). Resume and replay cannot share an authorization (`resource_id` + `action_type`
  active partial-unique index; distinct `action_type`; distinct idempotency-key namespaces
  `resume-auth:` / `replay-auth:`).
- PostgreSQL `statement_timestamp()` is authoritative everywhere; no Python clock governs validity.
- Every transition is a guarded CAS `UPDATE ... RETURNING`; a lost CAS returns `None` and is
  classified by an in-scope re-read.
- **Concurrent consume yields exactly one DB transition** — independently reproduced: 8 concurrent
  consumes on separate connections/transactions, exactly 1 winner, row consumed once
  (`test_concurrent_consume_yields_exactly_one_db_transition`).
- Expired / revoked / stale-version authorizations never consume (independently reproduced).
- **Rollback never leaves partial state** — a consume then forced rollback leaves the authorization
  unconsumed and still consumable (`test_consume_rollback_leaves_authorization_unconsumed`).
- Production-effect consume requires a production approval reference (see M-1 for the caveat); a
  general authorization can never substitute for production approval.
- No distributed exactly-once is claimed; this is a single-DB CAS. Correct.

## B. Scope isolation (repository + policy) — SOUND

- `team_id` / `project_id` are `UUID NOT NULL`; the scope predicate is exact null-safe equality
  (`IS NOT DISTINCT FROM $::uuid`). A NULL caller scope matches no row (fail-closed); a cross-scope
  id reads/affects 0 rows and is masked as `not_found` — existence never leaks. Independently
  reproduced (`test_null_and_cross_scope_direct_repo_calls_isolate`): correct scope reads; NULL,
  cross-team, cross-project all read nothing; a cross-scope consume affects 0 rows and does not
  consume.
- Dual-layer: the policy `_isolation_ok` denies cross/NULL scope AND the repository binds the same
  predicate, so a direct repository caller cannot bypass the policy layer.
- Replay scope: `production_effect` and the project boundary are derived SERVER-SIDE from the dead
  event's owning task (`outbox → clarification → operator_tasks`); an unresolvable owning task fails
  closed. `team_id` is actor-declared (documented — there is no team table upstream), but the
  authoritative isolation boundary is the globally-unique `project_id`, which is cross-checked
  against the owning task; a scope disagreement refuses the request. Acceptable.

## C. RBAC and actor separation — SOUND

- Canonical `shared/sdk/tasks/rbac.py:TASK_ROLES` is the only role vocabulary; the API-layer
  role sets are capability subsets of it, not a parallel system.
- Resume: Operator requests/cancels; the automated Policy/Safety Authority authorizes/rejects; a
  plain Operator can never human-authorize a resume (including their own). Service Identity
  consume-only.
- Replay: Operator requests; Approver authorizes/rejects; `requester != approver` enforced at BOTH
  the policy layer AND the DB `chk_rra_replay_two_person` constraint — the DB constraint blocks
  self-approval even on a direct repository call
  (`test_replay_two_person_db_constraint_blocks_self_approval`).
- Service Identity cannot request/authorize/reject/cancel; Policy Authority cannot consume; no role
  bypasses production approval at the system level.

## D. Policy Authority security — SOUND

- Requires BOTH an authenticated trusted principal (`X-Task-Actor` exactly equals
  `BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID`, an internal account) AND a server-side capability
  (`BE3_RESUME_POLICY_AUTHORITY_CAPABILITY[_PREVIOUS]`) over a dedicated header
  `X-Resume-Policy-Authority`.
- Comparison is constant-time (`hmac.compare_digest`), computed over EVERY configured slot with no
  short-circuit; both checks are computed before the single uniform `403 policy_authority_required`.
- Fail-closed: unset principal or unset capability → mechanism off (nothing matches); empty /
  oversized / malformed presented values rejected before any compare; an empty `_PREVIOUS` during
  rotation never becomes a valid empty credential. Independently reproduced
  (`test_policy_authority_capability_matching_fail_closed`,
  `test_policy_authority_uses_constant_time_compare`).
- **Header-logging check (mandatory):** no access-logging middleware logs request headers. FastAPI
  OTel instrumentation is default-configured (no `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*`), so
  it does not capture headers. The capability value is never placed in any log, audit payload,
  metric, span, or error/response body. No leakage path found.
- Policy Authority is restricted (`is_policy_authority` branch) to `authorize_resume` /
  `reject_resume` only.

## E. Resume transactions + command gate — SOUND

- Create / authorize / execution-preparation each run in a single caller transaction binding
  eligibility revalidation under row locks, the BE3-A authorization transition, the request
  transition, and durable audit/command evidence. The clarification active-slot CAS is claimed
  before the authorization insert so the authorization active-request index can never poison the
  transaction.
- Execution preparation: consume → outbox command insert → `execution_pending` transition. An
  outbox-insert failure raises and rolls back the whole unit including the consume — no consumed
  authorization is ever left without its command. Command gate off (`BE3_RESUME_COMMAND_ENABLED`
  default false) blocks the consume entirely.
- Duplicate prepare cannot create a second command (state gate + single-use consume); concurrent
  prepare yields exactly one transition; confirmation matches on `command_id`, and a conflicting
  terminal confirmation is rejected. No real orchestrator call exists anywhere.

## F. Command routing — SOUND

- `EVENT_DESTINATIONS` maps every allowlisted event type to exactly one destination, enforced at
  import time (`assert set(EVENT_DESTINATIONS) == ALLOWED_EVENT_TYPES`). `resume.execution_requested`
  is the only `orchestrator_command`; all others are `audit`. Unknown event type fails closed
  (`destination_for_event_type` raises).
- The BE2 audit relay's claim query is restricted to `audit_relay_claimable_event_types()`, so it
  can never claim, publish, or mark-published an orchestrator-command row. Independently reproduced
  against real Redis 7 (`test_audit_relay_never_claims_orchestrator_command_row`): the audit row was
  published; the command row stayed `pending`, `published_at` NULL.
- Destination is keyed off server-set `event_type` only; never request-payload controllable.

## G. Replay authorization (migration 034 + replay_*) — SOUND

- Only a `dead` row is replayable; published / non-dead / unknown-type / unknown-destination all
  rejected. Exactly one active request per event (partial unique index) — reproduced under
  concurrency: 6 concurrent requests for one event, exactly 1 succeeds
  (`test_one_active_replay_request_per_event_under_concurrency`).
- Two-person control at policy + DB layers. Service Identity executes internally only; **there is NO
  public execute / replay-now route** — verified by enumerating every `@router` decorator in
  `operations_replay_api.py` (5 routes: create/get/authorize/reject/cancel) and confirming
  `execute_authorized_replay` is only an internal service op.
- Destination readiness mandatory; production-effect derived server-side; unknown effect fails
  closed (treated as production). API + execution gates default off; when off, zero DB mutation
  (`test_feature_gates_off_produce_zero_side_effects`).

## H. Composite dead-episode state version — INDEPENDENTLY PROVEN DETERMINISTIC & COLLISION-FREE

`resource_state_version = f"{dead_at.isoformat()}:{attempts}"`. Re-derived, not accepted:

1. `dead_at` is written only by `outbox_relay._process_claimed` as `dead_at=statement_timestamp()`
   — PostgreSQL authoritative time. (Verified: it is the ONLY non-null writer of `dead_at` in
   production code; the two replay paths only set it NULL.)
2. `dead_at` is immutable while dead — the relay claim query selects `status='pending'` only, so a
   dead row is never re-touched by the relay.
3. `attempts` is frozen while dead — same reason; and `attempts` is only ever written non-decreasing
   (`plan_retry_state` increments; `plan_replay_state` preserves; INSERT default 0). It is
   **strictly monotonic across dead episodes**: replay preserves attempts (e.g. 5), the next failure
   increments to 6 before re-death. There is no decrement path.
4. Every path leaving-and-re-entering dead changes the snapshot: `attempts` strictly increases (5 →
   6 → …) AND `dead_at` is a new PG timestamp. Both components change.
5. No legal path yields the same snapshot for two different dead episodes of the same event — the
   monotonic `attempts` alone guarantees distinctness even if `dead_at` collided at microsecond
   resolution.
6–7. `dead_at` is `TIMESTAMPTZ`; asyncpg decodes it to a UTC-aware `datetime` independent of session
   timezone, and `.isoformat()` is a fixed, locale-independent representation. The snapshot is read
   through the same asyncpg path at request, authorize, and execute time, so no different-but-
   equivalent round-trip string arises.
8. The version comparison happens at the locked-row / CAS boundary: `lock_outbox_event`
   (`FOR UPDATE`) then compare; `replay_dead_row` re-locks (`FOR UPDATE`) and re-checks the version
   inside the CAS.
9. The client cannot supply or influence the snapshot — it is computed server-side from DB columns;
   no request body carries a version.
10. Independent of process locale/timezone (point 6–7).

Independently reproduced end-to-end (`test_dead_episode_version_changes_on_redeath_and_invalidates_stale_replay`):
episode-1 snapshot replays once (attempts preserved at 5, `dead_at` cleared, `published_at` NULL);
a stale episode-1 snapshot then fails the CAS with no mutation; after re-death (attempts 6, new
`dead_at`) the version differs and the episode-1 snapshot cannot replay episode 2. **A durable
monotonic `replay_state_version` column is therefore NOT required** — the existing composite already
provides a deterministic, collision-free, monotonic invariant. (A dedicated column would still be a
reasonable simplification, but its absence is not a defect.)

## I. replay_dead transaction composition — SOUND

- `replay_request_repository.replay_dead_row` is a distinct, transaction-aware function that runs
  inside the caller's transaction and never begins/commits/rolls back itself; the pre-existing
  `ClarificationOutboxRelay.replay_dead` (owns its own transaction) is unchanged. Both use the same
  `plan_replay_state` semantics — no contradictory replay behaviour. The new function adds a
  `resource_state_version` CAS guard.
- **Rollback restores everything** — independently reproduced
  (`test_replay_execution_rollback_restores_all_state`): with a READY provider the execute path
  consumes + requeues + transitions; a forced rollback reverts the consume, the dead-row requeue,
  and the request transition together; a subsequent committed execute succeeds exactly once. On
  success: `event_id`/`idempotency_key`/`event_type`/`destination`/`created_at` preserved, attempts
  NOT reset (still 5), `dead_at` cleared, `available_at` = PG time, `published_at` NULL.

## J. Replay retry semantics — SOUND

Manual replay is not a full retry reset: attempts is preserved (proven), so a row already at the cap
re-deads on the next failure (the documented bounded contract, not accidental). Business identity
(`event_id`/`idempotency_key`) preserved; duplicate execute cannot replay twice (single-use consume
+ `authorized→executed` CAS + one-active-request index).

## K. Destination readiness — SOUND

Default provider reports `not_configured` for both destinations; nothing (env/body/header) spoofs it
to ready. not_configured / unhealthy / disabled / unknown-destination all block execution WITHOUT
consuming the authorization, mutating the dead row, or marking the request executed — the request
stays `authorized` and only a `replay.execution_blocked` audit row is written. Independently
reproduced (`test_destination_not_ready_blocks_execution_without_any_mutation`).

## L. Rate limiting — SOUND for the hard cap; soft per-actor cap (finding L-1)

- Defaults: 3 successful replays/event/24h; 10 requests/actor/24h. Bounds validated; invalid/
  out-of-range config fails closed (rejects, never clamps). PostgreSQL time authoritative.
- The **per-event successful-replay hard cap** cannot be exceeded under concurrency: request
  creation for one event is serialized by the one-active-request-per-event partial unique index, so
  successive successful replays are inherently serial and the count check `>= 3` blocks the 4th.
  The successful-replay cap also cannot be bypassed by a new idempotency key.
- **Finding L-1 (Medium, deferred):** the per-actor request cap is a COUNT check with no per-actor
  lock. Under a simultaneous burst across distinct events it can overshoot — independently measured:
  a per-actor cap of 2 with 8 concurrent requests created all 8. Sequential enforcement is exact
  (the next request is `rate_limited`). This weakens one of several storm mitigations; it does NOT
  compromise any authorization/scope/production/state-version property, and the safety-critical
  per-event cap is index-serialized. See Findings.

## M. Production-effect review — SOUND derivation; reference resolution deferred (finding M-1)

- `production_effect` is derived server-side from the owning task's own column, never from request
  input; unresolvable owner fails closed (treated as production). Neither replay nor resume
  authorization substitutes for production approval.
- **Finding M-1 (Medium, deferred):** the `production_approval_reference` is checked only for
  non-emptiness — it is NOT resolved to a real, non-expired, non-revoked, correct-resource
  production approval. This is a documented, intentional BE3 scope boundary (BE3-A record:
  "BE3-A neither creates nor validates production approval itself"; the separate production gate is
  the enforcement point). Independently reproduced
  (`test_production_approval_reference_is_only_nonempty_checked`): a production-effect consume
  succeeds with a bogus non-empty reference; an absent reference is correctly blocked. See Findings.

## N. Audit and privacy — SOUND

Audit/command payloads are built through positive key allowlists with a forbidden-substring guard
(`password/secret/token/dsn=/postgres:///redis://`), bounded lengths, and scalar-only values — never
raw clarification/answer/replay content, capability values, secrets, DSNs, or credentials. Reason
codes are bounded enums. Metrics labels are event types, not high-cardinality IDs. Errors mask
cross-scope existence as `not_found`; authorization failures never echo the expected capability.
Replay audit events are identity-separated from the original business event (they carry identifiers
about the mutation, not a second copy of the business event).

## O. Feature gates and activation boundary — SOUND

`BE3_RESUME_API_ENABLED`, `BE3_RESUME_COMMAND_ENABLED`, `BE3_REPLAY_API_ENABLED`,
`BE3_REPLAY_EXECUTION_ENABLED` all default false, read from the process environment only (exact
`"true"`), never request-overridable. API gate off → 503 with zero DB access; execution/command gate
off → zero consume/outbox/replay mutation. No shared compose/helm/k8s config enables any gate; no
shared migration applied; no startup/runtime auto-worker starts the relay or any replay/resume loop
(the orchestrator lifespan starts only the pre-existing approval listener + workflow-event consumer,
unchanged).

## P. Migrations 032 / 033 / 034 — SOUND

Additive-only (new tables only; no column added to an existing table; no backfill). UUID scope
types NOT NULL; FK-absence on scope columns is documented and sound (no upstream team table;
`operator_tasks.project_id` itself carries no FK). Partial unique indexes correctly scoped to the
active-state set. Up / down / reapply verified (the review test suite and the BE3 suites apply all
six migrations from scratch repeatedly). Down migrations drop only their own table (no data delete,
no cross-stage impact). Compatible with existing rows (existing tables untouched).

---

## Findings

**Critical:** none.
**High:** none.

**Medium — M-1 (deferred; mandatory activation precondition).** `production_approval_reference` is
validated for non-emptiness only, not resolved to a real production approval. Documented BE3 scope
boundary; no production effect is reachable in this disabled foundation
(`production_executed_true_count` = 0). *Required before any production-effect resume/replay
activation:* resolve the reference against the authoritative production-approval registry (existence,
not-expired, not-revoked, correct-resource, correct-effect) at consume time, and add this to
`be3-runtime-activation-gate.md`. Does not block code merge of the disabled foundation.

**Medium — L-1 (deferred; hardening before activation).** The per-actor replay-request rate limit is
a non-locking COUNT check and can overshoot under a concurrent burst. The per-event successful-replay
hard cap and the one-active-request-per-event invariant are index-serialized and safe. *Recommended
before relying on the per-actor cap as a hard limit at activation:* make it concurrency-safe (e.g.
a per-actor advisory lock or a serializable insert-count guard), and record it in the activation
gate. Does not block code merge of the disabled foundation.

**Low — L-2 (informational).** In `authorization_policy.evaluate`, the `authorize_replay` two-person
check is skipped when `requested_by is None`. In practice the service always passes the NOT NULL
`requested_by`, and the DB `chk_rra_replay_two_person` constraint is the unconditional backstop, so
this is not exploitable; consider making the policy-layer check unconditional for clarity.

**Deferred:** M-1 and L-1 are the two items to carry into the runtime-activation-gate before the
corresponding activation. Nothing else is deferred.

## Safety confirmations

- No shared migration applied; no deployment; no gate activated outside the reviewer's own ephemeral
  containers. No real orchestrator/resume/replay execution in any shared runtime.
- Draft PR #20 remained Draft/OPEN/unmerged and untouched.
- `production_executed_true_count` = 0.
- Isolated ephemeral PostgreSQL 16 and Redis 7 were created for testing and destroyed afterwards;
  the shared test stack's PostgreSQL/Redis containers were byte-for-byte the same (identical
  container IDs) before and after.

## Recommendation

BE3-A + BE3-B + BE3-C are **code-merge-ready as a disabled-by-default foundation** (BE3_TECHNICAL_
VERDICT: PASS). Before any runtime activation, close M-1 (production-approval reference resolution)
and L-1 (concurrency-safe per-actor rate cap) and fold both into `be3-runtime-activation-gate.md`.
Merge (BE3-M) and any activation each require separate explicit Product Owner authorization.

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, or credentials appear in this record — only neutral labels ("internal
test runtime", "isolated ephemeral PostgreSQL 16", "isolated ephemeral Redis 7")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
