# AT-D13 — AT-M2 canonical merge authorization

> **Product Owner decision record. Authorizes merging the validated AT-M2 candidate into
> `main`. Authorizes no production action, no external action, no AT-M3 implementation and no
> PCP remediation. `production_executed_true_count: 0`.**

```text
AT-D13:                      RESOLVED / BINDING
Recorded_on:                 2026-08-21
Recorded_by:                 Product Owner
Canonical_main_at_decision:  192ebb74ba600f7a53ddf5967a7254a1f7a72fb8
Validated_candidate:         c984140995240f9b2d9c3932b9e7b716c4773035
Depends_on:                  AT-D11 (docs/decisions/at-m2-authorization.md),
                              AT-D12 (docs/decisions/at-d12-successor-freeze-amendment.md)
```

## 1. What this record is for

AT-D11 authorized the AT-M2-TEAM-CORE implementation milestone but explicitly authorized "no
further milestone" and said nothing about merging that work into `main`. This record is that
separate authorization: the Product Owner approves canonicalizing the validated AT-M2 candidate
branch (`at-m2-team-core`) into `main`. It is the only place the merge authorization is recorded.

## 2. What is authorized

```text
Merge scope:                  fast-forward canonicalization of the validated candidate into main
Documentation-only authority: this record and the reconciliation commit it authorizes
Post-merge verification:      bounded source-of-truth checks only
```

## 3. What is NOT authorized

```text
Production action              NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization       NOT GRANTED -- unchanged
AT-M3 implementation           NOT AUTHORIZED -- each future milestone still needs its own decision
PCP remediation                NOT AUTHORIZED by this record
Unrelated runtime changes      NOT AUTHORIZED -- this record covers the merge only
```

## 4. Governance Validation 2 — actually performed, evidence recorded here

AT-GOV-VALIDATION-1 (2026-08-21) found one genuine blocker: the guard-split implementation
commit (`9c002e0`) was itself outside the window `SUCCESSOR_AUTHORIZED_CHANGESET_END` recorded,
because that field still named the implementation commit's own parent. AT-GOV-REMEDIATION-1
closed it with a single metadata-only commit (`c984140`) repointing the field at the immutable
implementation commit, verified before and after commit against five adversarial proofs (check30
pass, simulated same-path post-end edit rejected, simulated new unauthorized post-end path
rejected, invalid/missing end fails closed, historical guards unaffected).

Governance Validation 2 re-ran the full evidence chain independently against the pushed candidate
`c984140995240f9b2d9c3932b9e7b716c4773035`, fresh, before this record was written:

```text
Regression suite (15 directly-affected + meta-guard files): 1021 passed, 2 failed
Failures:                     test_66d_decisions_untouched_by_this_remediation,
                               test_rm1_verifier_passes (check23)
Failure classification:       pre-existing, unrelated -- independently reproduced identically on
                               the pre-AT-GOV-IMPLEMENT-1 commit via git worktree/stash before any
                               governance-split change existed; touch unrelated 66D contract docs
                               from a different, closed stage
New governance regressions:   0
check30 (verify_step66d_align1_delivery_decision_model.py): PASS
verify_at_m1_architecture_reset.py:                          PASS (244 checks, 0 failures)
test_at_d12_successor_freeze_amendment.py:                   58/58 PASS
SUCCESSOR_AUTHORIZED_CHANGESET_END fixed-not-tailing probe:  PASS (end=9c002e0, HEAD=c984140,
                                                               distinct; live_guard_end() still
                                                               resolves "HEAD"; only
                                                               docs/governance/AI_AGENTS_PM_STATE.md
                                                               changed since the recorded end)
```

Validation 2 PASS. No blockers. No Validation 3 required or permitted.

## 5. What this decision does NOT do

```text
Does NOT authorize AT-M3 .. AT-M8            -- each still needs its own decision
Does NOT grant production authorization      -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D11 or AT-D12
Does NOT move SUCCESSOR_AUTHORIZED_CHANGESET_END -- it stays pinned at 9c002e0
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
