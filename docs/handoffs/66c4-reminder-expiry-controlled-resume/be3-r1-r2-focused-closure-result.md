# Step 66C.4-BE3-R-FC → Focused Findings-Closure Result Handoff

> **Result handoff only. Records the outcome of the focused closure of BE3-R findings M-1, L-1, R2-1
> by the ORIGINAL independent reviewer. Authorizes NO merge, NO deployment, NO shared-migration
> application, NO gate activation. Draft PR #20 remains Draft/OPEN/unmerged. Append-only: does not
> modify the original BE3-R verdict/findings/evidence.**

## Verdict

```
STEP66C4_BE3_R1_R2_FOCUSED_CLOSURE_VERIFY: PASS   (closure process + artifacts complete)
BE3_TECHNICAL_VERDICT: PASS                        (M-1, L-1, R2-1 all independently CLOSED)
```

## What was closed

- **M-1** (production-approval reference resolution): `production_action_approvals` registry
  (migration 035) + a transaction-aware `resolve_and_consume_approval` resolver, wired into the ONE
  shared `authorization_service.consume()` used by both resume and replay. Resource/action/team/
  project/state-version/time-bound, single-use, revocable, durably decided; FOR UPDATE lock (no
  TOCTOU); consumed atomically in the same transaction as the authorization consume; a post-approval
  authz-CAS failure raises to force full rollback. Every invalid/stale/expired/revoked/wrong-scope/
  wrong-resource/wrong-action reference fails closed with no consume. **CLOSED.**
- **L-1** (per-actor replay rate cap concurrency): `pg_advisory_xact_lock(hashtextextended(...))`
  keyed on team+project+actor (server-side hash, not Python `hash()`), acquired before the dead-row
  lock, xact-scoped; the count is now scoped by (team, project, actor). 20-way/50-way bursts never
  exceed the cap; per-scope isolation; idempotent-retry counted once; rolling-window; admin no
  bypass; invalid config fails closed; per-event 3-success cap unchanged. **CLOSED.**
- **R2-1** (resume production-effect): derived server-side from `operator_tasks.production_effect`
  under the task lock, fail-closed, folded into the canonical `resource_state_version`, revalidated
  at request+authorize+consume; `production_effect` removed from the API schema (client cannot
  supply/upgrade/downgrade). **CLOSED.**

## Independent evidence (not the implementation's own verifiers)

- Isolated ephemeral PostgreSQL 16 on an internal test runtime (no Redis needed for these findings).
- Independent focused-closure suite `tests/test_step66c4_be3_r1_r2_focused_closure.py` = **22 passed,
  0 skipped**. Combined mandatory run (that suite + BE3-R1/R2 + BE3-A/B/C + B-C1) = **140 passed, 0
  skipped** (repeated on the final formatted bytes). BE1/BE2 regression = **75 passed, 0 skipped**.
- `scripts/verify_step66c4_be3_r1_r2_focused_closure.py` structural verifier PASS.
- ruff / black --check / mypy / `git diff --check` / secret-scan clean on the reviewer's added files.
- Positive inversion: the original M-1 finding-demonstration test now FAILS unchanged against the
  fixed head (bogus reference rejected) — confirming the fix; the historical test was not modified.
- Ephemeral container + detached worktree destroyed afterwards; shared PostgreSQL/Redis containers
  byte-for-byte identical (same IDs) before and after.

## Findings

- New Critical/High: none. New activation-blocking Medium (related to the remediations): none.
- Observation (non-blocking, R2-obs-1): the API silently drops an unrecognized client-sent
  `production_effect` field (Pydantic default) — consistent with existing API convention, cannot
  influence classification (proven). Optional `extra="forbid"` hardening; not required.

## Activation gate

`be3-runtime-activation-gate.md` §A.0/§A.1 record M-1/L-1/R2-1 as code-level CLOSED while preserving
the original 11 activation prerequisites (not marked complete) and the NO-deployment / NO-shared-
migration / NO-activation posture. **Deployment readiness — NO; Runtime activation readiness — NO;
Shared migration readiness — NO.**

## Posture

```
BE3-R1/R2 remediation: implemented (feature head 5a413bf) | Focused closure: COMPLETE (independent)
Findings M-1 / L-1 / R2-1: CLOSED -> BE3_TECHNICAL_VERDICT: PASS
PR #20: Draft / NOT FOR MERGE / untouched | Shared migration: none | Deployment: none | Activation: none
Runtime resume/replay: none in any shared runtime | production_executed_true_count: 0
Next authorization required: Product-Owner-authorized BE3-M merge decision. No activation.
```

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, usernames, or credentials appear in this record — only neutral labels._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
