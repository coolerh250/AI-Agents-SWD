# Step 66C.4-BE3-P — Implementation Slicing Plan

> **Planning/contract document only. No implementation authorized. Each slice below requires its own
> explicit Product Owner authorization before it may begin.**

## Verification policy (new)

```text
- BE3-A, BE3-B, BE3-C are completed by ONE implementation flow (the same session may build all three).
- After the WHOLE of BE3 (A+B+C) is complete, exactly ONE independent security/transaction review runs
  (BE3-R). It is NOT split per slice.
- If BE3-R raises findings, the ORIGINAL reviewer performs a focused closure of those findings; a new
  fresh reviewer is NOT spun up by default.
- BE3-M merges only after Product Owner authorization, following the BE1-M/BE2-M non-squash pattern.
```

## Slices

### BE3-A — Authorization model, repository and policy enforcement

```text
Allowed files:   migrations/<next>_be3_resume_replay_authorization.sql (new authorization + request
                 tables); shared/sdk/tasks/*authorization*.py (model + repository + policy check);
                 tests/test_step66c4_be3_a_*.py.
Forbidden files: apps/**/main.py route registration; any resume/replay EXECUTION; frontend/**;
                 infra/helm/k8s/.github; migration 031 edits; existing producer files.
Entry criteria:  BE3-P PASS + PO authorization of BE3-A.
Exit criteria:   durable authorization record + request repository + policy enforcement, single-use/
                 time-bound/state-version-bound semantics, unit + isolated-PG tests green; NO route,
                 NO execution, NO activation.
Tests:           authorization single-use/expiry/state-version; RBAC permission functions; two-person
                 rule; reason-code allowlist; no-content/secret in records.
Risk:            medium (new schema, no runtime effect).
Review:          part of the single BE3-R after A+B+C.
```

### BE3-B — Resume request, authorization and execution command

```text
Allowed files:   apps/orchestrator/src/*.py resume endpoints (registered but dispatch GATED/DISABLED-
                 BY-DEFAULT); shared/sdk/tasks/*resume*.py; tests/test_step66c4_be3_b_*.py.
Forbidden files: enabling dispatch by default; production-effect bypass; frontend/**; deployment;
                 public replay endpoint; producer cutover.
Entry criteria:  BE3-A complete + PO authorization of BE3-B.
Exit criteria:   resume request/authorize/reject/cancel endpoints with RBAC, 403/404-mask/409,
                 durable authorization, gated execution command (dispatch_enabled=false), orchestrator
                 confirmation handler; isolated PG/Redis tests green.
Tests:           full resume state machine; CAS/idempotency; concurrency scenarios D1-D9; gated
                 dispatch stays off; audit evidence for every transition.
Risk:            high (touches the orchestrator command path, gated).
Review:          part of the single BE3-R.
```

### BE3-C — Replay request, authorization and internal replay adapter

```text
Allowed files:   apps/orchestrator/src/*.py replay endpoints; shared/sdk/tasks/*replay*.py adapter
                 that calls the existing internal replay_dead under a durable authorization;
                 tests/test_step66c4_be3_c_*.py.
Forbidden files: exposing replay_dead as a public/direct endpoint (must go through request+auth);
                 Admin Console direct repository access; service-identity self-authorization.
Entry criteria:  BE3-A complete + PO authorization of BE3-C.
Exit criteria:   replay request/authorize/reject/cancel endpoints with two-person control, only-dead
                 eligibility, single-use authorization, dead->pending via the internal adapter only
                 (replay_dead is never a public/direct endpoint), preserved
                 event_id/idempotency_key/attempts; isolated PG/Redis tests green.
Tests:           full replay state machine; two-person control; only-dead; already-replayed no-op;
                 identity preserved; authorization single-use/expiry.
Risk:            high (replay has downstream duplicate potential; internal-only + authorized).
Review:          part of the single BE3-R.
```

### BE3-R — Independent security/transaction review

```text
Scope:           one independent security + transaction review over the whole of BE3-A+B+C.
Allowed:         review artifacts, isolated PG/Redis re-tests, a review verifier/tests, progress update.
Forbidden:       modifying implementation, merging, deploying, activating.
Verdict:         BE3_TECHNICAL_VERDICT: PASS | REMEDIATION_REQUIRED (recorded separately from the
                 process marker). On findings, the ORIGINAL reviewer performs a focused closure.
Risk:            n/a (review).
```

### BE3-M — Merge after Product Owner authorization

```text
Scope:           non-squash merge commit (BE1-M/BE2-M pattern), preserving all evidence commits.
Entry criteria:  BE3-R final PASS + explicit PO merge authorization.
Forbidden:       squash/rebase; deployment; migration application to a shared DB; activation; producer
                 cutover; BE3 capability turn-on.
Exit criteria:   MERGED / NOT DEPLOYED / NOT RUNTIME VALIDATED / NOT ACTIVATED.
```

## Statement

Planning/contract document only. No implementation authorized. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
