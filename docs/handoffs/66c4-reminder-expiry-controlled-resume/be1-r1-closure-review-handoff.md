# Step 66C.4-BE1-R1 → Closure Review Handoff

> **Handoff document. PR #17 remains Draft and unmerged. The remediation session does NOT approve
> a merge and does NOT declare technical closure.**

## What the closure reviewer must review

```text
Branch:            feature/66c4-be1-lifecycle-outbox-foundation
Baseline reviewed
by BE1-R:          d2467f5
Remediation commit: see the branch tip after Step 66C.4-BE1-R1
Draft PR:          #17
Independent review
being closed:      review/66c4-be1-technical-security-migration @ f5417f4
                   STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS
                   BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

## Reviewer independence requirements (binding)

```text
Executed by:       a FRESH Claude Code review subagent in an INDEPENDENT session and an
                   INDEPENDENT git worktree.
Must NOT be:       the BE1 implementation session, or the BE1-R1 remediation session.
Must NOT receive:  the remediation session's private reasoning, scratch notes, uncommitted files,
                   or any pre-written verdict.
Must judge from:   the canonical contract, the PO decisions, the exact commits, the committed
                   records, the code, the migration and the tests.
Must NOT:          fix anything it finds, merge PR #17, or deploy.
```

## Markers -- never conflate

```text
STEP66C4_BE1_R1_REMEDIATION_VERIFY  -- the remediation session's own static self-verification.
STEP66C4_BE1_R1_PG_EVIDENCE         -- whether the mandatory PostgreSQL suite really ran with
                                       zero skips.
BE1_TECHNICAL_VERDICT               -- the TECHNICAL result. Only the independent closure reviewer
                                       may set this to PASS. Neither marker above is a technical
                                       verdict, and a green verifier is not closure.
```

## What must be independently re-verified

```text
1. B-1 closure. Reproduce the transaction-crossing scenario on an isolated ephemeral PostgreSQL 16:
   a transaction that BEGAN before due_at and executes the committed CAS AFTER due_at must be
   REJECTED, and answered_at must remain NULL. Confirm the negative control -- that the SAME
   scenario still SUCCEEDS against the old `due_at > now()` predicate -- so the regression test is
   proven non-vacuous rather than taken on trust.
2. answered_at is claim-statement time and is not backdated to transaction start.
3. Strict boundary: due_at exactly equal to the compared statement timestamp is REJECTED.
4. The canonical contract no longer asserts per-statement now() semantics anywhere, and the binding
   predicate in the contract matches the implemented predicate.
5. B-2 closure. available_at / dead_at / bounded last_error exist with the documented constraints;
   binding 11.3 failure modes 1 and 7 are now simultaneously satisfiable; retry, dead and operator
   replay semantics are defined in the canonical contract, not only in code.
6. Migration 031 up / down / reapply on a fresh isolated database: additive, deterministic, no
   table rewrite, no legacy row mutation, only BE1 objects removed on rollback.
7. M-1 closure. Re-run the bypass probes against the positive allowlist, plus any new probe the
   reviewer devises. The reviewer should specifically attempt bypasses the remediation did NOT
   anticipate.
8. Disabled-foundation posture: zero live producers, zero relays, zero schedulers, zero runtime
   outbox writes; audit/event transport unchanged relative to main.
9. Destructive PostgreSQL fixtures are genuinely fail-closed: verify the guard REFUSES a shared or
   unconventional database name and refuses without the opt-in, rather than merely documenting it.
10. Scope: no frontend, infra, helm, k8s or workflow change; no resume endpoint, authorization,
    dispatch or workflow resume; no deployment.
```

## Known open items the closure reviewer should NOT treat as regressions

```text
L-1, L-2, L-3 are recorded as DEFERRED in be1-deferred-low-findings.md with reasons and a
recommended future stage. They were deliberately not fixed. The reviewer may disagree with a
deferral and say so, but their presence is disclosed, not hidden.
Repository-wide ruff/black/mypy failures exist in files untouched by BE1 and BE1-R1. They are
pre-existing baseline noise; the affected-file results are reported separately from repo-wide
results in the test record.
```

## Authorization posture carried into the closure review

```text
PR #17:         Draft, unmerged. Merge remains unauthorized.
Step 66C.4-BE2: NOT authorized, NOT started.
Codex:          NOT authorized.
Claude Design:  NOT authorized.
Deployment:     NOT authorized. No shared test, staging or production deployment occurred.
```

## Statement

Handoff document only. No scheduler. No relay. No live producer. No resume/dispatch. No external
notification. No shared-runtime migration. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
