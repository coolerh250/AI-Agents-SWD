# Step 66C.4-BE3-P-M — Planning Merge and Source-of-Truth Record

> **Planning merge record. The BE3 resume/replay authorization CONTRACT is now canonical source of
> truth on main. NO BE3 runtime capability is implemented, deployed, or activated. BE3-A requires a
> separate, explicit Product Owner authorization.**

## Merge

```text
Method:            non-squash merge commit (two parents preserved; no squash, no rebase)
Pre-merge main:    33b776b
Reviewed head:     81f38d2 (PR #19 head at merge; --match-head-commit enforced)
Merge commit:      90fc765
Merge parents:     33b776b (main) + 81f38d2 (planning branch)
Final main:        90fc765
PR #19:            MERGED (Ready, not Draft)
```

## What merged (planning artifacts only)

```text
docs/contracts/66c4-reminder-expiry-controlled-resume/
  be3-operator-resume-replay-authorization-contract.md
  be3-rbac-permission-matrix.md
  be3-resume-replay-state-machine.md
  be3-api-event-contract.md
  be3-security-and-threat-model.md
  be3-runtime-activation-gate.md
  be3-implementation-slicing-plan.md
docs/handoffs/66c4-reminder-expiry-controlled-resume/be3-implementation-handoff.md
scripts/verify_step66c4_be3_planning.py
tests/test_step66c4_be3_planning.py
source/progress.md
docs/alignment/66-project-completion/master/next-executable-stage-sequence.md
```

The diff 33b776b..90fc765 contains NO apps/**, shared/**, migrations/**, services/**, frontend/**,
infra/**, helm/**, k8s/**, or .github/workflows/** change. Contract only.

## Canonical decisions now source-of-truth

```text
- RBAC reuses the six canonical shared/sdk/tasks/rbac.py TASK_ROLES (no second RBAC).
- Resume + replay state machines with per-transition actor/precondition/idempotency/tx-boundary/
  audit/failure; replay only-dead, event_id/idempotency_key preserved, attempts never reset.
- Durable authorization: resource-bound, action-bound, single-use, time-bounded, state-version-bound,
  revocable; two-person replay control (requester != approver); service identity executes only.
- API /operations/resume-requests + /operations/replay-requests with 403/404-mask/409/idempotency;
  single durable destination; at-least-once + state-bound idempotency; exactly-once NOT claimed.
- Runtime activation gate: 11 prerequisites, dispatch DISABLED-BY-DEFAULT, replay internal-only.
- Slicing: BE3-A -> BE3-B -> BE3-C (one flow), one independent BE3-R review (original-reviewer
  focused closure), BE3-M non-squash merge after PO authorization.
```

## Status

```text
Step 66C.4-BE3-P:  MERGED / PRODUCT CONTRACT READY
Step 66C.4-BE3-A:  NEXT CANDIDATE / NOT AUTHORIZED
Step 66C.4-BE3:    DESIGNED / NOT IMPLEMENTED / NOT DEPLOYED / NOT ACTIVATED
```

## Authorization posture (unchanged by this merge)

```text
Backend/API/repository implementation: NONE
Migration added/applied:               NONE (migration 031 NOT applied to any shared DB)
Resume/replay endpoint:                NONE created
replay_dead:                           internal-only, no public/runtime caller
Worker/relay activation:               NO
Deployment:                            NO
Step 66C.4-BE3-A:                      NOT authorized, NOT started
Codex / Claude Design:                 NOT authorized
Review evidence branches:              PRESERVED
production_executed_true_count:        0
```

## Statement

Planning merge record only. No implementation, no API, no migration, no deployment, no activation.
No dispatch/resume/replay executed. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
