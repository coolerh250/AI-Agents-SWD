# Step 66C.4-BE1-R1 Remediation Record

> **Remediation of the Step 66C.4-BE1-R blocking findings. No scheduler. No relay. No live
> producer. No resume/dispatch. No deployment. No merge. PR #17 remains Draft.**

## Inputs

```text
Baseline implementation:    feature/66c4-be1-lifecycle-outbox-foundation @ d2467f5
Latest main:                e03c22d
Independent review:         review/66c4-be1-technical-security-migration @ f5417f4
Review process marker:      STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS
Technical verdict acted on: BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

The reviewer's original artifacts and verdict are NOT modified by this stage. This record is the
remediation RESPONSE and is kept separate from the review findings themselves.

## Independent review evidence carried into PR #17

The reviewer's six findings documents, its result handoff, its stage records and its test record
are carried onto this branch BYTE-IDENTICAL from `f5417f4`, so PR #17 contains the full review
trail. Their technical verdict (`BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`) and their
experimental results are unchanged and were not rewritten.

Two review files were deliberately NOT carried onto this branch:
`scripts/verify_step66c4_be1_independent_review.py` and
`tests/test_step66c4_be1_independent_review.py`. Those assert that the DEFECTS are PRESENT at
commit d2467f5 -- for example that the CAS still reads `due_at > now()`, that the outbox lacks
`available_at`, and that the payload guard accepts a nested `{"meta": {"answer": ...}}`. They are
point-in-time findings evidence, and by design they FAIL once the findings are remediated. Carrying
them would have left a red suite on the branch, and editing them to pass would have meant rewriting
review evidence, which this stage is forbidden to do. They remain intact and unmodified on
`review/66c4-be1-technical-security-migration` @ `f5417f4`, which is the citable record. The
closure reviewer should read them there, and can confirm that each defect they pin is exactly what
`tests/test_step66c4_be1_r1_remediation.py` now pins as FIXED.

## Findings remediated

```text
B-1 (BLOCKING)  PostgreSQL now()/transaction_timestamp() freeze at transaction BEGIN, so a
                transaction opened before due_at could claim after it and backdate answered_at.
                -> Remediation A (canonical contract) + Remediation B (CAS predicate).
                Status: FIXED.

B-2 (BLOCKING)  The outbox lacked a persisted retry schedule, a terminal death timestamp and a
                bounded failure reason, making binding 11.3 failure modes 1 and 7 mutually
                unsatisfiable.
                -> Remediation C (contract + migration 031) + Remediation D (repository model).
                Status: FIXED.

M-1 (MEDIUM)    The payload guard inspected only top-level keys against an exact-match deny list;
                nested payloads and near-miss key names were accepted.
                -> Remediation E (positive per-event-type allowlist, scalar-only values).
                Status: FIXED.

Test gaps       No transaction-crossing test, near-tautological boundary test, timing-dependent
                concurrency test, silent PostgreSQL skips, destructive fixtures with no
                ephemerality guard.
                -> New mandatory tests + fail-closed guard + separated PostgreSQL evidence marker.
                Status: FIXED.

L-1, L-2, L-3   Deferred by design; recorded in be1-deferred-low-findings.md. NOT fixed here.
```

## Files changed

```text
Canonical contract:
  lifecycle-and-time-contract.md, data-model-contract.md, api-and-event-contract.md,
  race-condition-and-failure-analysis.md, observability-and-audit-plan.md,
  scheduler-architecture-decision.md, implementation-stage-slicing-plan.md,
  test-and-validation-plan.md, product-owner-decision-checklist.md

Migration:
  migrations/031_clarification_lifecycle_outbox_foundation.sql (+ _down.sql)

Runtime:
  shared/sdk/tasks/workroom_store.py      (one CAS predicate + answered_at/updated_at stamps)
  shared/sdk/tasks/lifecycle_outbox.py    (durability mapping, positive allowlist, state models)

Tests / verification:
  tests/step66c4_pg_safety.py (new), tests/test_step66c4_be1_r1_remediation.py (new),
  tests/test_step66c4_be1_data_model_deadline_outbox.py (updated for the corrected API),
  scripts/verify_step66c4_be1_r1_remediation.py (new)

NOT changed: apps/orchestrator/src/workroom_api.py behavior, shared/sdk/audit/**,
  shared/sdk/event_bus/**, apps/retry-scheduler/**, apps/communication-gateway/**, frontend/**,
  infra/**, helm/**, k8s/**, .github/workflows/**.
```

## Authorization posture

```text
PR #17:                     Draft, unmerged. This session does NOT approve a merge.
Step 66C.4-BE2:             NOT authorized, NOT started.
Codex:                      NOT authorized.
Claude Design:              NOT authorized.
Independent closure review: REQUIRED (Step 66C.4-BE1-R1-R), by a FRESH review subagent in an
                            independent session and worktree. This remediation session must not
                            perform it and must not interpret its own verifier PASS as technical
                            closure.
```

## Statement

Remediation implementation record only. No scheduler implemented or activated. No outbox relay
implemented or activated. No live producer cutover. No runtime outbox write. No resume endpoint,
authorization, dispatch or workflow resume. No audit/event transport change. No external
notification. No shared test/staging/production deployment. No production or external action. No
merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
