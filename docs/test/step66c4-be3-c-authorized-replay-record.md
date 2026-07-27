# Step 66C.4-BE3-C — Test & Validation Record

> **Test record. Two-person-controlled dead-event replay FOUNDATION only. NOT deployed. NOT
> activated. All PostgreSQL work ran on an isolated ephemeral container, destroyed afterward. NOT
> FOR MERGE.**

## Marker

```text
STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS   (self-verification; combined BE3-R still required)
```

## Environment

```text
Runtime:   internal test runtime (isolated ephemeral PostgreSQL 16 container), created for this run
           and destroyed afterward. Isolated DB name step66c4_be3c (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:  detached at feature head 2949e20 with the uncommitted BE3-C files overlaid; removed after
           the run (twice -- once during development, once as a final confirmation of the exact
           formatted/committed bytes). The shared aiagents-test stack was NOT touched.
Redis:     NOT required. Destination-readiness tests use an injectable stub provider; no real
           consumer of either destination exists in this codebase.
```

## Results

### BE3-C authorized dead-event replay (real PostgreSQL 16)

```text
tests/test_step66c4_be3_c_authorized_replay.py -> 27 passed / 0 skipped / 0 failed
```

Coverage:
- **Migration:** 034 up/down/reapply; constraints/indexes; NOT NULL scope columns; existing BE1/BE2
  rows compatible.
- **Eligibility:** a dead event succeeds; a pending event is `not_dead`; a published event is
  `already_published`; cross-scope/NULL scope masked (`not_found_masked`).
- **Request/idempotency/concurrency:** duplicate idempotency key returns the canonical same request;
  a distinct key on an already-active event is `active_request_exists`; concurrent requests yield
  exactly one active request (exercising the `request_authorization` savepoint composability fix).
- **Actors/two-person:** an unauthorized role (`requester`) cannot request; a Service Identity cannot
  request or authorize; an Operator requests; a DIFFERENT Approver authorizes; the SAME principal
  who requested (even holding an approver-eligible role) cannot self-approve
  (`requester_cannot_approve`); a human cannot execute.
- **Authorize/cancel race:** exactly one legal outcome (`canceled` XOR `authorized`).
- **Execution:** command/execution gate off → no consume, no mutation; destination not ready → no
  consume, no mutation, request stays `authorized` (retryable), one `replay.execution_blocked`
  evidence row; a valid execution preserves `id`/`idempotency_key`/`event_type`/`created_at`, does
  NOT reset `attempts`, increments the dead-episode version (`dead_at`/`attempts` changes on the
  next death), and durably marks the request `executed`; concurrent execution yields exactly one
  applied replay; a stale authorization (event mutated after authorize) cannot execute
  (`stale_state`).
- **Rollback:** a post-consume `replay_dead_row` guard failure rolls back the consume (request stays
  `authorized`, dead row untouched); an audit-insertion failure rolls back the WHOLE execution
  (consume + dead-row mutation both undone); a process failure before commit leaves no partial state.
- **Rate limiting:** bounded requests per actor per window (`rate_limited` on the 3rd of a 2-max
  window); bounded successful replays per event (`rate_limited` on the 2nd success after a 1-max
  cap, even though the event validly died again).
- **Production effect:** derived from the owning task's OWN `production_effect` column — never from
  request input — and still requires the separate production approval reference before consume.
- **Privacy:** every `replay.*` outbox payload carries no secret/token/DSN.
- **Maintenance:** `expire_due_replay_requests` transitions an expired-authorization request to
  `expired`.

DB-less unit tests (5): feature-gate defaults; the dead-episode state-version composite changes only
when `dead_at` or `attempts` changes; rate-limit config bounds + fail-closed on invalid/out-of-range
values; the default destination-readiness provider always reports `not_configured` (never `ready`)
for both known destinations and `unknown_destination` for an unrecognized one; the replay audit
payload builder rejects unsafe/unknown keys; the reused (unchanged) BE3-A two-person policy applies
to `action_type='replay'`.

### Regression (real PostgreSQL 16)

```text
BE3-A foundation/C1/C2, BE1 data-model/deadline/outbox, BE1-R1, BE2 poller/relay, BE2-R1, Step 66C.1
operator/workroom API, Step 66B.1 task API, Step 66B.3 RBAC/audit, BE3-B, BE3-B-C1, plus BE3-C
-> 253 passed / 5 skipped(non-mandatory) / 0 failed.
```

The 5 skips are pre-existing Redis-dependent BE2 relay tests; non-mandatory and unrelated. Two
BE1/BE1-R1 "no live outbox producer" static guards and the BE2-R1 "no public/runtime/startup caller
of replay_dead" static guard were EXTENDED (not weakened) to recognize `replay_service.py` (the
authorized internal caller) and `replay_request_repository.py` (the authorized `replay_dead_row`
adapter definition) — exactly as BE3-B did for `resume_service.py`. Both guards still fail on any
OTHER unexpected reference. Prose-only mentions of the literal token "replay_dead" in
`replay_request_model.py`, `operations_replay_api.py`, and `main.py` were reworded (not allowlisted),
consistent with the BE3-A precedent for this exact false-positive pattern.

## Quality gates (local)

```text
ruff check (changed Python files):  PASS
black --check (changed Python files): PASS
mypy (changed modules):              PASS
git diff --check:                    PASS
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_c_authorized_replay.py: PASS
```

## Posture

```text
Public API: /operations/replay-requests (DISABLED-BY-DEFAULT via BE3_REPLAY_API_ENABLED)
Execution: internal only, BE3_REPLAY_EXECUTION_ENABLED-gated; no endpoint; readiness-gated (never
           ready by default -- no consumer exists for either destination)
replay_dead called in any shared runtime: NO  |  event published: NO
Shared DB migration: NO  |  worker/relay/consumer activation: NO  |  deployment: NO  |  frontend: NO
production_executed_true_count: 0
BE3-A + BE3-B + BE3-C: all complete (self-verified)  |  PR: Draft #20 / NOT FOR MERGE
Combined BE3-R: REQUIRED, NOT YET AUTHORIZED
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
