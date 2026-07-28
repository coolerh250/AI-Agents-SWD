# Step 66C.4-BE3-M — Merge and Source-of-Truth Record

> **Merge/closure record. BE3 is MERGED to main but NOT DEPLOYED, NOT RUNTIME VALIDATED, NOT
> ACTIVATED. No shared migration (032/033/034/035) is applied to any shared database. All BE3
> feature gates remain disabled-by-default. No resume/replay execution has ever occurred
> (`production_executed_true_count` = 0).**

## Merge

```text
Method:            non-squash merge commit (two parents preserved; no squash, no rebase)
Pre-merge main:    5745ab7
Reviewed head:     5a413bf (PR #20 head at merge; --match-head-commit enforced)
Merge commit:      284d706
Merge parents:     5745ab7 (main) + 5a413bf (feature)
Final main:        284d706
PR #20:            MERGED (was Draft -> Ready -> merged)
```

## Evidence chain (preserved, not squashed)

```text
BE3-A authorization foundation:        da758f2
BE3-A contract alignment:              1164464
BE3-A NULL-scope closure:              c2bc5cb
BE3-B operator-controlled resume:      962963f
BE3-B-C1 authority/routing alignment:  2949e20
BE3-C authorized replay:               6323972
Original combined independent review:  5626403  (review/66c4-be3-combined-security-transaction)
BE3-R1 findings remediation (M-1/L-1): b1bac36
BE3-R2 remediation (R2-1):             5a413bf
Focused closure (M-1/L-1/R2-1):        2712ad4  (review/66c4-be3-combined-security-transaction,
                                                  NOT merged to main -- reviewer-only branch)
```

The focused-closure commit `2712ad4` lives on the original reviewer's own branch, not on main; per
the review-branch preservation rule it was never merged. Its verdict is recorded here as evidence,
not re-derived.

## Verdicts (recorded separately, never conflated)

```text
-- Original BE3-R combined independent review:
STEP66C4_BE3_COMBINED_INDEPENDENT_REVIEW_VERIFY: PASS   (process marker)
Original BE3_TECHNICAL_VERDICT: PASS (code-merge readiness of the disabled foundation), with two
  Medium findings (M-1, L-1) recorded as MANDATORY ACTIVATION PRECONDITIONS, not merge blockers.

-- BE3-R1 remediation (M-1, L-1):
STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY: PASS   (self-verification)

-- BE3-R2 remediation (R2-1):
STEP66C4_BE3_R2_RESUME_PRODUCTION_EFFECT_VERIFY: PASS   (self-verification)

-- Focused closure (M-1, L-1, R2-1), by the ORIGINAL independent reviewer:
STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS   (process marker)
Final BE3_TECHNICAL_VERDICT: PASS   (all three findings independently CLOSED)
```

The original review's own `BE3_TECHNICAL_VERDICT: PASS` (scoped to code-merge readiness with
activation preconditions) and the focused closure's `BE3_TECHNICAL_VERDICT: PASS` (scoped to
finding closure) are two distinct, separately-recorded verdicts from the same reviewer at two
points in time. Neither overwrites the other.

## What closed (M-1 / L-1 / R2-1)

```text
M-1 (production approval reference resolution): migration 035 production_action_approvals -- a
    team/project/resource/action/state-version/time-bound, single-use, revocable-before-consume
    registry -- with a FOR-UPDATE-locked resolve_and_consume_approval resolver wired into the ONE
    shared authorization_service.consume() integration point (both resume and replay). Fail-closed
    on missing/unknown/invalid/revoked/expired/consumed/wrong-scope/wrong-resource/wrong-action/
    stale-version references; consumed in the SAME transaction as the authorization consume.
L-1 (replay rate-limit concurrency): pg_advisory_xact_lock (keyed on team_id+project_id+actor_id,
    server-side hash, acquired before any row lock) serializes the count-then-insert sequence;
    count itself scoped by (team_id, project_id, requested_by). 20-concurrent/cap-10 -> exactly 10;
    50/cap-3 -> exactly 3; per-scope isolation; idempotent-retry counted once.
R2-1 (resume production-effect classification): now derived server-side from
    operator_tasks.production_effect under the existing task row lock, folded into
    resource_state_version, revalidated at authorize AND consume time; removed entirely from the
    API request schema and service signature -- no code path for a client to supply, upgrade, or
    downgrade it.
```

## Source-of-truth status

```text
Step 66C.4-BE3:
  MERGED
  NOT DEPLOYED
  NOT RUNTIME VALIDATED
  NOT ACTIVATED
  NO SHARED MIGRATION

Sub-stages:
  BE3-A  -- MERGED
  BE3-B  -- MERGED
  BE3-C  -- MERGED
  BE3-R  -- PASS (combined independent review; two Medium findings recorded, now closed)
  BE3-R1/R2 findings (M-1, L-1, R2-1) -- CLOSED (focused closure by the original reviewer)
  BE3-M  -- PASS (this record)

Next candidate: runtime activation planning (all 11 activation-gate prerequisites in
  be3-runtime-activation-gate.md remain OPEN; each requires its own separate Product Owner
  authorization).
```

## Authorization posture (unchanged by the merge)

```text
Shared deployment (test/staging/production):        NO
Migrations 032/033/034/035 applied to a shared DB:   NO
Lifecycle poller / outbox relay / command consumer
  activation for BE3 resume/replay:                  NO
BE3_RESUME_API_ENABLED:                              false (default, unchanged)
BE3_RESUME_COMMAND_ENABLED:                          false (default, unchanged)
BE3_REPLAY_API_ENABLED:                              false (default, unchanged)
BE3_REPLAY_EXECUTION_ENABLED:                        false (default, unchanged)
Runtime resume / replay / dispatch:                  NO
Production approval runtime grant:                   NO (internal foundation only, no HTTP router)
Codex / Claude Design:                               NOT authorized
Review evidence branches:                            PRESERVED (review/66c4-be3-combined-security-
                                                      transaction and all prior BE1/BE2 review
                                                      branches; none deleted)
production_executed_true_count:                      0
```

## Statement

Merge/closure record only. No deployment. No shared-runtime migration. No scheduler/relay/consumer
activation. No feature-gate enablement. No resume/replay execution. No production or external
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
