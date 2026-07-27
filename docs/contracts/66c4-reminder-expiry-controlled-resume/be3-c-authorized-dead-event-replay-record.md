# Step 66C.4-BE3-C — Authorized Dead-Event Replay

> **Implementation record. Two-person-controlled dead-event replay FOUNDATION on the shared BE3
> feature branch (Draft PR #20, NOT FOR MERGE). No real replay_dead call in any shared runtime, no
> deployment, no worker/relay activation. This completes BE3-A+B+C on this branch; the combined
> independent BE3-R security/transaction review over all three is the next required gate.**

Marker: `STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS` (self-verification only).

## What BE3-C adds

```text
migrations/034_be3_replay_requests.sql (+ _down)     -- durable replay_requests table (additive)
shared/sdk/tasks/replay_request_model.py             -- states, reason codes, gates, rate-limit
                                                          policy, readiness kinds, safe audit payload
shared/sdk/tasks/replay_request_repository.py        -- transaction-aware CAS repo + locks +
                                                          transaction-aware replay_dead_row adapter
shared/sdk/tasks/replay_service.py                   -- eligibility + readiness + rate-limit +
                                                          authorization + execution orchestration
apps/orchestrator/src/operations_replay_api.py       -- /operations/replay-requests API
                                                          (DISABLED-BY-DEFAULT)
shared/sdk/tasks/lifecycle_outbox.py                 -- + replay.* audit events (destination: audit)
shared/sdk/tasks/authorization_service.py            -- request_authorization savepoint fix (below)
```

## Preflight findings (§3)

- **replay_dead current transaction behavior:** `ClarificationOutboxRelay.replay_dead` (BE1/BE2)
  ALWAYS owns and commits its own transaction (`tx = connection.transaction(); await tx.start()`),
  even when a caller passes in a connection. It CANNOT be composed atomically with an authorization
  consume in a single transaction. Per §3's instruction, a NEW transaction-aware internal variant
  was built (`replay_request_repository.replay_dead_row`) rather than chaining two independent
  transactions. The existing `ClarificationOutboxRelay.replay_dead` is UNCHANGED (still used only by
  its own pre-existing tests) — no caller of it was modified.
- **attempt/dead_at/available_at behavior:** unchanged (BE1's `plan_replay_state`, reused as-is by
  the new adapter): attempts NOT reset, `available_at` reset to statement time, `dead_at`/`last_error`
  cleared.
- **row identity/idempotency fields:** `id`, `idempotency_key`, `event_type`, `payload`, `created_at`
  are all preserved verbatim by both the existing relay method and the new adapter.
- **destination classification:** reused unchanged from BE3-B-C1 (`EVENT_DESTINATIONS`); every
  `replay.*` audit event added here is classified `DESTINATION_AUDIT` (evidence about the replay,
  never a second business-event copy).
- **state-version mechanism:** none existed for the outbox row before this stage (see §7 below).
- **transaction-aware repository support:** the existing `authorization_repository`/
  `resume_request_repository` pattern (take the caller's connection, run inside the caller's
  transaction, never commit/rollback) was followed exactly for `replay_request_repository`.

## Resource-state-version decision (§7)

Rather than adding a `replay_state_version BIGINT` column to the already-merged
`clarification_lifecycle_outbox` table (031), a replay request snapshots
`f"{dead_at.isoformat()}:{attempts}"` — the **dead episode composite** — as its
`resource_state_version`. This is durable and CAS-safe because:
- `dead_at` is set exactly once per pending→dead transition (the relay's dead-branch), never touched
  while the row is `pending`, and cleared to `NULL` only by a replay.
- `attempts` is frozen the instant a row goes dead (the relay's claim query only ever touches
  `status='pending'` rows), so it cannot change while dead.
- The composite is therefore unique per "distinct dead episode": if the SAME row is later replayed
  and dies again, `dead_at` changes to a new value, so a request/authorization bound to the OLD
  episode is rejected (`stale_state`) at authorize/execute time — proven by
  `test_pg_stale_authorization_cannot_execute`.

No migration 034 column was needed for this; `dead_episode_state_version` is a pure function over
two pre-existing, already-tested columns — equivalent CAS safety to a dedicated version column,
fully exercised by the test suite.

## Authorization reuse (unchanged from BE3-A)

`authorization_service`/`authorization_policy` are used with `action_type='replay'`,
`resource_type='outbox_event'` **exactly as-is** — no code change to their business logic. The
`chk_rra_replay_two_person` DB constraint and the policy's `two_person_required` check (requester !=
approver) already existed and apply automatically. Approver roles are the canonical
`{reviewer_approver, platform_admin}` from `shared/sdk/tasks/rbac.py`; no second RBAC was created.

## Composability fix: `request_authorization` savepoint (§3 preflight → real bug found)

Resume's `request_resume` avoids ever hitting `authorization_service.request_authorization`'s
`UniqueViolationError` recovery path by claiming the clarification's `resume_requested_at IS NULL`
slot BEFORE calling it — so two concurrent resume requests never race inside
`request_authorization` itself. Replay has **no equivalent pre-existing claim column** on the
already-merged outbox table, so two concurrent replay requests for the SAME dead event **do** reach
`request_authorization` concurrently, and the loser's `create_request` raises
`asyncpg.UniqueViolationError` on `uq_rra_active_request`. The existing except-block then executes a
recovery `fetchrow` — which, called from **within an already-open caller transaction** (as BE3-B/C's
services do), would raise `asyncpg.InFailedSQLTransactionError` instead of returning a clean result,
because a failed statement aborts the whole enclosing PostgreSQL transaction, not just the Python
exception. **Fix:** `repo.create_request` inside `request_authorization` now runs inside its own
`async with conn.transaction():` — which asyncpg automatically promotes to a SAVEPOINT when the
caller already has an outer transaction open — so a `UniqueViolationError` there only rolls back to
that savepoint, leaving the caller's outer transaction healthy for the recovery query and any
subsequent statements. `replay_service.request_replay` additionally wraps its own
create-authorization + insert-replay-request pair in a savepoint for the same reason. This is a
backward-compatible robustness fix (still-unmerged BE3-A code, same feature branch); it changes no
successful-path behavior and is exercised by `test_pg_concurrent_request_exactly_one_active`.

## Feature gates (disabled-by-default, env-only)

```text
BE3_REPLAY_API_ENABLED=false        -- the whole /operations/replay-requests router 503s when off
BE3_REPLAY_EXECUTION_ENABLED=false  -- execute_authorized_replay does NOTHING when off
```

## Destination readiness (§15)

`execute_authorized_replay` accepts an injectable `readiness_provider`; the DEFAULT
(`replay_request_model.default_destination_readiness`) reports **every** destination
`not_configured` — because neither the BE2 audit relay nor any orchestrator-command consumer is
activated in any shared runtime. Real execution is therefore always blocked in every real deployment
of this codebase today, independent of the execution feature gate. Tests inject an explicit stub
readiness provider to exercise the success path deterministically; no shared consumer is built or
assumed.

## Rate limiting (§16)

Server-side, DB-derived, bounded, fail-closed: `BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT` (default 3,
range [1,100]) and `BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS` (default 24, range [1,168]) and
`BE3_REPLAY_MAX_REQUESTS_PER_ACTOR` (default 10, range [1,1000]). An unparsable or out-of-range value
raises (fail-closed), never silently clamps. No role — including `platform_admin` — bypasses the cap
at the policy layer; raising it is a separate, explicit, deployed configuration change.

## Production-effect derivation (§17)

`production_effect` is derived **server-side** from the dead event's owning task's own
`production_effect` column (`clarification_lifecycle_outbox.clarification_id → …task_id →
operator_tasks.production_effect`) — **never** trusted from request input (the create-request body
carries only an optional `production_approval_reference`, a label, never a boolean toggle). An
unresolvable scope/task fails closed (treated as production-effect, blocking consume without an
approval reference) — proven by `test_pg_production_effect_derived_not_client_trusted`.

## `replay.execution_blocked` is not a state transition

When destination readiness fails, the replay request is **not** mutated — it stays `authorized` (a
later attempt can proceed once the destination becomes ready) — only an audit-evidence row
(`replay.execution_blocked`) is written. No authorization is consumed and no dead row is touched.

## Verification

```text
STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS
Tests: see docs/test/step66c4-be3-c-authorized-replay-record.md (isolated ephemeral PostgreSQL 16;
0 failed / 0 skipped). ruff / black / mypy clean. No real replay_dead call in any shared runtime, no
event published, no BE2 relay/consumer activated, no shared migration/deployment.
production_executed_true_count = 0. Draft PR #20 NOT merged.
```

This completes BE3-A + BE3-B + BE3-C as one implementation flow on `feature/66c4-be3-resume-replay-
authorization`. The combined independent security/transaction review (**BE3-R**) over all three is
the next required gate before any merge or activation — see
`docs/handoffs/66c4-reminder-expiry-controlled-resume/be3-abc-to-combined-review-handoff.md`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
