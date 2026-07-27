# Step 66C.4-BE3-B-C1 — Test & Validation Record

> **Targeted alignment test record. Policy authority authentication boundary + command outbox
> destination routing. NOT deployed. NOT activated. All PostgreSQL work ran on an isolated
> ephemeral container, destroyed afterward. NOT FOR MERGE.**

## Marker

```text
STEP66C4_BE3_B_AUTHORITY_ROUTING_ALIGNMENT_VERIFY: PASS   (self-verification; combined BE3-R still required)
```

## Environment

```text
Runtime:   internal test runtime (isolated ephemeral PostgreSQL 16 container), created for this run
           and destroyed afterward. Isolated DB name step66c4_be3b_c1 (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:  detached at feature head 962963f with the uncommitted BE3-B-C1 files overlaid; removed
           after the run. The shared aiagents-test stack was NOT touched.
Redis:     NOT required. The destination-routing tests use a stub event bus (_RaisingBus, tracks a
           call counter) so the audit relay's claim query is proven never to touch a command row
           without depending on any live broker.
```

## Results

### BE3-B-C1 alignment (real PostgreSQL 16)

```text
tests/test_step66c4_be3_b_c1_authority_routing_alignment.py -> 18 passed / 0 skipped / 0 failed
```

Coverage:
- **Policy authority (DB-less):** constant-time comparison used (`hmac.compare_digest`, no plain
  `==`/`!=` on the secret); current+previous rotation matching; unset server config can never be
  satisfied; the resolved role is not one of the six TASK_ROLES; permission scope is
  authorize_resume/reject_resume ONLY (request/cancel/consume all denied `policy_authority_scope`).
- **Policy authority (real PG / API):** feature-gate-off never runs the capability comparison (the
  comparison function is mocked to raise if called); an unauthenticated caller with a
  correct-looking capability header is denied before the capability is even inspected; the
  presented/expected capability value never appears in the response body of a denial.
- **Command outbox destination (DB-less):** every allowlisted event_type has an explicit
  destination; `resume.execution_requested` is the only DESTINATION_ORCHESTRATOR_COMMAND type; an
  unclassified event_type raises; the audit relay's claimable set excludes the command destination.
- **Command outbox destination (real PG):** the audit relay's claim query never claims (and its
  event bus is never even called for) a command row; a row inserted OUT OF BAND with an unknown
  event_type is likewise never claimed (fail-closed by construction, not a denylist); the command
  gate closed creates no command row; with no active consumer, a command row's backlog count stays
  at 1 across repeated audit-relay cycles (untouched, blocking activation); a concurrent
  `prepare_execution` race yields exactly one command identity; a retried `prepare_execution` after
  success creates no second command row/identity; audit evidence (resume.requested/.authorized) and
  command evidence (resume.execution_requested) are always distinct outbox rows (own id + own
  idempotency_key), never overwriting each other.

### Regression (real PostgreSQL 16)

```text
BE3-A foundation/C1/C2, BE1 data-model/deadline/outbox, BE1-R1, BE2 poller/relay, BE2-R1, Step 66C.1
operator/workroom API, Step 66B.1 task API, Step 66B.3 RBAC/audit, BE3-B (updated for the
trusted-principal model), plus BE3-B-C1 -> 226 passed / 5 skipped(non-mandatory) / 0 failed.
```

The 5 skips are pre-existing Redis-dependent BE2 relay tests (no isolated ephemeral Redis configured
for this run); non-mandatory and unrelated to this change. The pre-existing BE3-B API capability test
(`test_api_feature_gate_and_capability`) was UPDATED (not weakened) to also configure the trusted
principal id and to authenticate the authorize call as that principal — reflecting the corrected
model, since the old test's "any authenticated actor + capability" pattern is exactly the gap this
stage closes. `outbox_relay.py`'s claim-query and backlog-sampler changes are fully backward
compatible: every pre-existing audit event type is still claimed/published/sampled exactly as
before (proven by the unchanged BE2 relay regression); only the new command destination is excluded.

## Quality gates (local)

```text
ruff check (changed files):       PASS
black --check (changed files):    PASS
mypy (changed modules):           PASS
git diff --check:                 PASS
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_b_c1_authority_routing_alignment.py: PASS
```

## Posture

```text
Public API: unchanged (/operations/resume-requests, still DISABLED-BY-DEFAULT)
Orchestrator call: NO  |  resume executed: NO  |  replay_dead called: NO  |  event published: NO
Shared DB migration: NO  |  worker/relay activation: NO  |  deployment: NO  |  frontend: NO
BE3-C: NOT implemented  |  PR: Draft / NOT FOR MERGE  |  Combined BE3-R: REQUIRED
production_executed_true_count: 0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
