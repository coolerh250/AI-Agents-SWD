# Step 66C.4-BE3-R2 — Resume Production-Effect Test & Validation Record

> **Test record. Closes finding R2-1 (resume production-effect was client-controllable). NOT
> deployed. NOT activated. All PostgreSQL work ran on an isolated ephemeral container, destroyed
> afterward. NOT FOR MERGE.**

## Marker

```text
STEP66C4_BE3_R2_RESUME_PRODUCTION_EFFECT_VERIFY: PASS
```

## Environment

```text
Runtime:   internal test runtime (isolated ephemeral PostgreSQL 16 container), created for this run
           and destroyed afterward. Isolated DB name step66c4_be3r2 (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:  detached at feature head b1bac36 (Step 66C.4-BE3-R1) with the uncommitted BE3-R2 files
           overlaid; removed after the run. The shared aiagents-test stack was NOT touched.
Redis:     not required (no destination-selection/transport path changed in this remediation).
```

## Results

### New: BE3-R2 resume production-effect (real PostgreSQL 16 + DB-less)

```text
tests/test_step66c4_be3_r2_resume_production_effect.py -> 14 passed / 0 skipped / 0 failed
```

Coverage:
- **Client cannot control classification:** `resume_service.request_resume` has no
  `production_effect` parameter at all (inspected via `inspect.signature`, not merely "ignores an
  extra kwarg"); `ResumeRequestCreate` has no `production_effect` field, and a client that still
  sends the old field name in a raw payload is silently dropped by Pydantic and never reaches the
  service layer.
- **Client downgrade has no effect:** task `production_effect=true` → the created request/
  authorization is observably `production_effect=True`, and consume is correctly blocked
  (`production_approval_required`) with no way for the client to have made it otherwise.
- **Client upgrade attempt has no effect:** task `production_effect=false` → the created request/
  authorization is observably `production_effect=False`, and consume proceeds without requiring a
  production approval.
- **State-version binding:** the state-version string demonstrably changes when only
  `production_effect` changes (all other fields held equal), and is stable when it does not.
- **State-change races, all three required scenarios:**
  - non-production at request → task becomes production before authorize → `authorize_resume`
    returns `stale_state`; the authorization is left `pending`/unconsumed (no decision that could
    later execute).
  - non-production at authorize → task becomes production before consume → `prepare_execution`
    returns `stale_state`; the authorization remains unconsumed.
  - production at request → task becomes non-production before consume → `prepare_execution`
    returns `stale_state` (the reverse direction also correctly invalidates).
- **Production approval integration (reused from BE3-R1, unmodified):** an authoritative
  production-effect task with no approval blocks consume with zero outbox mutation; a REAL,
  resource-bound, state-version-matched approval lets consume succeed and is durably marked
  `consumed`; an approval granted for a DIFFERENT clarification is rejected
  (`production_approval_wrong_resource`); an approval granted with a stale resource_state_version is
  rejected (`production_approval_stale_state`).
- **Scope isolation:** a cross-project task lookup is masked as `not_found_masked`; a NULL actor
  scope is masked the same way (fail-closed); the correctly-scoped request succeeds.
- **Transaction rollback:** an outbox-insertion failure during `prepare_execution` rolls back BOTH
  the BE3 authorization consume AND the production approval consume together — verified by directly
  querying both `resume_replay_authorizations.consumed_at` (NULL) and
  `production_action_approvals.state` (`granted`, unchanged) after the forced failure.

### Regression (real PostgreSQL 16)

```text
BE1 data-model/deadline/outbox, BE1-R1, BE2-R1, BE3-A foundation, BE3-B operator-resume, BE3-B-C1
authority/routing alignment, BE3-C authorized replay, BE3-R1 findings remediation, plus BE3-R2
-> 193 passed / 0 skipped / 0 failed.
```

179 (prior full regression, unchanged) + 14 (BE3-R2) = 193, matching exactly. Two pre-existing
BE3-B/BE3-R1 tests that constructed a resume with `production_effect=` passed through the request
were updated (not weakened) to seed the OWNING TASK's own column instead, since the parameter no
longer exists — no assertion was loosened; the same scenarios (blocked-without-approval,
invalid-reference-rejected, valid-approval-succeeds) are still fully exercised. Replay's own
production-effect derivation (`replay_request_repository.resolve_event_scope`) was not touched —
confirmed unchanged by the unmodified, still-passing `tests/test_step66c4_be3_c_authorized_replay.py`
suite.

## Quality gates (local + remote)

```text
ruff check (changed Python files):    PASS
black --check (changed Python files): PASS
mypy (changed modules):               PASS
git diff --check:                     PASS (benign CRLF-on-touch warnings only)
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_r2_resume_production_effect.py: PASS
```

## Posture

```text
Resume production_effect: now derived server-side from operator_tasks.production_effect at all
                           three resume entry points (request/authorize/consume), under the SAME
                           task row lock already used for eligibility; folded into
                           resource_state_version so a classification change invalidates any
                           outstanding request/authorization.
Replay production_effect: unchanged (already server-derived per the BE3-R review).
Production approval integration: unchanged, reused from BE3-R1.
Shared DB migration: NO (none required)  |  worker/relay/consumer activation: NO  |  deployment: NO
New public HTTP endpoint: NO  |  frontend: NO
production_executed_true_count: 0
BE3-R2: findings-closure complete (self-verified)  |  PR: Draft #20 / NOT FOR MERGE
Next: the original combined independent reviewer's focused closure over M-1/L-1/R2-1 remains the
      next required gate before BE3-M (non-squash merge), which itself requires separate explicit
      Product Owner authorization.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
