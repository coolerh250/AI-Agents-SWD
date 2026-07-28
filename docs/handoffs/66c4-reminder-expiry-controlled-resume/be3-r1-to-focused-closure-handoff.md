# Step 66C.4-BE3-R1 → Focused Closure Handoff

> **Result handoff only. Records the outcome of the BE3-R1 required findings remediation (M-1, L-1).
> Authorizes NO merge, NO deployment, NO shared-migration application, NO gate activation. Draft PR
> #20 remains Draft/OPEN/unmerged.**

## Verdict

```text
STEP66C4_BE3_R1_FINDINGS_REMEDIATION_VERIFY: PASS
```

Both findings recorded by the BE3-R combined independent review as mandatory activation
preconditions are now closed at the code level:

- **M-1** — `production_approval_reference` now resolves against an authoritative,
  transaction-locked registry (`production_action_approvals`, migration 035) — existence, state
  (granted/not consumed/not revoked/not expired), and full binding (action/resource/team/project/
  resource_state_version) — for BOTH the resume and replay consume paths, via the ONE shared
  `authorization_service.consume` integration point.
- **L-1** — the per-actor replay-request rate limit is now concurrency-safe (a PostgreSQL
  transaction-scoped advisory lock serializes the check-then-insert sequence) and correctly isolated
  per (team_id, project_id, actor_id) — a related, previously-unflagged global-count gap was closed
  in the same change.

## What was NOT authorized or attempted

- No new BE3 capability beyond what M-1/L-1 required to close.
- No frontend, no runtime activation, no deployment, no shared migration application, no feature-gate
  enablement, no shared resume/replay execution, no destination-architecture change.
- No public grant/revoke HTTP endpoint for production approvals — internal-service-only in this
  stage (a deliberate, recorded scope boundary — see `be3-r1-m1-production-approval-contract.md` §2.8).
- PR #20 was not touched, not switched out of Draft, not merged.

## Independent evidence (real PostgreSQL, not just the implementation's own claims)

- Isolated ephemeral PostgreSQL 16 on an internal test runtime, destroyed afterward; shared stack
  untouched.
- New suite `tests/test_step66c4_be3_r1_findings_remediation.py`: **17 passed, 0 skipped**.
- Full regression (BE1/BE1-R1/BE2-R1 + BE3-A/B/B-C1/C + BE3-R1): **179 passed, 0 skipped, 0 failed**.
- Two pre-existing tests that had encoded the M-1 gap as expected behavior were UPDATED (not
  weakened) to assert the new, correct, fail-closed behavior.
- `scripts/verify_step66c4_be3_r1_findings_remediation.py`: PASS.
- ruff / black / mypy / `git diff --check` / secret-scan: clean.
- Migration 035 up/down/reapply independently verified.

## Process note: the M-1 architecture blocker

Preflight investigation found no existing table in this codebase models a production-effect approval
bound to BE3's team/project/resource/action model — this was recorded as an architecture blocker per
the operator's own stop condition, rather than faked shut with a mismatched or stubbed registry. The
Product Owner then explicitly directed: build a dedicated new registry, but only after a short
planning checkpoint recording the derivable design (cited from canonical governance) and surfacing
the genuine open decisions. Three such decisions were asked and answered (2026-07-28): approval
binding is **resource-scoped and single-use** (not task-scoped/reusable); validity uses the **same
1s-24h bound** as every other BE3 request; the state-version question was **N/A** given the
resource-scoped answer. See `be3-r1-m1-production-approval-contract.md` for the full record.

## Next authorized step

BE3-R1 closes the two findings the combined review required before activation; it does not itself
authorize merge or activation. `be3-runtime-activation-gate.md` §A.0 now records both closures.
BE3-M (non-squash merge of PR #20) may proceed only after separate explicit Product Owner
authorization. Runtime activation is a further, separate authorization after the full activation gate
(items 1-11) is met.

## Posture

```text
BE3-A/B/C: complete (self-verified) | BE3-R: complete (independent, PASS) | BE3-R1: complete (self-verified)
PR: Draft #20 / NOT FOR MERGE / untouched | Shared migration: none | Deployment: none | Activation: none
New HTTP endpoint: none | production_executed_true_count: 0
Next authorization required: explicit PO authorization for BE3-M.
```

---
_Non-production only. No production action. No production data. No internal IP addresses, SSH
aliases, private hostnames, usernames, or credentials appear in this record — only neutral labels._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
