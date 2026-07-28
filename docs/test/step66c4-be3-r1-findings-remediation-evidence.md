# Step 66C.4-BE3-R1 — Findings Remediation Test & Validation Record

> **Test record. Closes BE3-R findings M-1 and L-1. NOT deployed. NOT activated. All PostgreSQL work
> ran on an isolated ephemeral container, destroyed afterward. NOT FOR MERGE.**

## Marker

```text
STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY: PASS
```

## Environment

```text
Runtime:   internal test runtime (isolated ephemeral PostgreSQL 16 container), created for this run
           and destroyed afterward. Isolated DB name step66c4_be3r1 (fail-closed guard; not shared).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed).
Worktree:  detached at feature head 6323972 (Step 66C.4-BE3-C) with the uncommitted BE3-R1 files
           overlaid; removed after the run. The shared aiagents-test stack was NOT touched.
Redis:     not required for this remediation (no destination-selection/transport path changed).
```

## Results

### New: BE3-R1 findings remediation (real PostgreSQL 16)

```text
tests/test_step66c4_be3_r1_findings_remediation.py -> 17 passed / 0 skipped / 0 failed
```

Coverage:
- **M-1, direct repository level:** missing / unknown / syntactically-invalid reference all rejected
  (`not_found` / `invalid_reference`); revoked, expired, and already-consumed approvals all rejected
  with distinct reason codes; wrong team / wrong project / wrong resource / wrong action / stale
  resource-state-version all rejected (`wrong_scope` / `wrong_resource` / `wrong_action` /
  `stale_state`) and the approval is left completely untouched after every rejected attempt;
  concurrent revoke-vs-consume on the SAME approval yields exactly one safe outcome (never both,
  never neither).
- **M-1, end-to-end through the shared resolver:** both the RESUME and the REPLAY consume path (both
  going through the ONE shared `authorization_service.consume`) are exercised independently — an
  invalid reference never lets either authorization consume (and, for replay, never mutates the dead
  outbox row); a REAL granted, resource-bound approval lets both succeed, and the approval is
  observably `consumed` and points at the correct `consumed_by_authorization_id` afterward.
- **L-1:** 20 concurrent requests (same actor/team/project, cap=10) create exactly 10, the rest
  `rate_limited`; a 50-way concurrent burst (cap=3) never exceeds the hard cap; a concurrent retry of
  the SAME idempotency key produces exactly one durable row, counted once; different actors have
  independent limits; the SAME actor in a DIFFERENT (team, project) scope has an independent limit
  (isolated); `platform_admin` cannot bypass the hard cap; the rolling window correctly excludes
  aged-out requests; an invalid rate-limit config (`BE3_REPLAY_MAX_REQUESTS_PER_ACTOR=0`) fails
  closed (raises, no side effect).
- **DB-less (3):** the production-approval reason-code allowlist is enforced; the audit-payload
  builder rejects an unsafe value and an unknown reason code; only the canonical `reviewer_approver`/
  `platform_admin` roles may grant/revoke a production approval.

### Pre-existing tests updated (not weakened) for the new correct behavior

Two pre-existing tests previously asserted, as DOCUMENTED/EXPECTED behavior, that an arbitrary
non-empty `production_approval_reference` string would let a production-effect consume succeed —
exactly the M-1 gap. Both were updated to assert the NEW correct behavior (a bogus reference is
rejected; only a real, resolvable, granted approval succeeds) rather than deleted or loosened:

```text
tests/test_step66c4_be3_a_authorization_foundation.py::test_pg_production_gate_blocks_consume_without_reference
tests/test_step66c4_be3_b_operator_resume.py::test_pg_production_effect_independently_gated
```

Both now additionally prove: a bogus reference is rejected with `production_approval_invalid_reference`;
a real granted approval lets the consume proceed and is durably marked `consumed`, referencing the
correct authorization; and (BE3-A test only) the SAME approval cannot back a second consume
(single-use) and a stale resource_state_version is independently rejected by the approval's own CAS.

### Regression (real PostgreSQL 16)

```text
BE1 data-model/deadline/outbox, BE1-R1, BE2-R1, BE3-A foundation, BE3-B operator-resume, BE3-B-C1
authority/routing alignment, BE3-C authorized replay, plus BE3-R1
-> 179 passed / 0 skipped / 0 failed.
```

75 (BE1/BE1-R1/BE2-R1) + 87 (BE3-A/B/B-C1/C) + 17 (BE3-R1) = 179, matching exactly. No historical
BE1/BE2/BE3-A/B/C verifier or test was weakened; the two updated tests above are UPDATES to reflect
the closed finding, not removals.

Migration 035 up/down/reapply was independently verified directly against the ephemeral instance
(table created, dropped, re-created, re-applied idempotently with no error) in addition to being
exercised by every `_reset_and_migrate` call in the new test file.

## Quality gates (local + remote)

```text
ruff check (changed Python files):    PASS
black --check (changed Python files): PASS
mypy (changed modules):               PASS
git diff --check:                     PASS (benign CRLF-on-touch warnings only)
Secret / internal-identifier scan of committed files: PASS
scripts/verify_step66c4_be3_r1_findings_remediation.py: PASS
```

Note: the PRE-EXISTING `scripts/verify_step66c4_be3_c_authorized_replay.py` (BE3-C's own verifier,
scoped to BE3-C's own migrations 032-034) reports a structural mismatch when run against a worktree
that ALSO has the new, out-of-scope-for-BE3-C migration 035 overlaid — this is expected (BE3-C's
verifier was never updated to know about BE3-R1) and is not evidence of a regression; BE3-C's own
TESTS (`tests/test_step66c4_be3_c_authorized_replay.py`, part of the 179-test regression above) still
pass unchanged. The BE3-C verifier itself was NOT modified (modifying a prior stage's verifier to
"fix" this would be exactly the kind of weakening this project's rules forbid).

## Posture

```text
Production approval reference: now resolved against an authoritative, transaction-locked registry
                                (migration 035) for BOTH resume and replay -- not just checked
                                non-empty.
Per-actor replay rate limit: now concurrency-safe (PostgreSQL advisory lock) and scoped by
                              (team_id, project_id, actor_id).
Shared DB migration: NO  |  worker/relay/consumer activation: NO  |  deployment: NO  |  frontend: NO
New public HTTP endpoint: NO (grant/revoke remain internal-only service functions this stage)
production_executed_true_count: 0
BE3-R1: findings-closure complete (self-verified)  |  PR: Draft #20 / NOT FOR MERGE
Next: BE3-M (non-squash merge) requires separate explicit Product Owner authorization.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
