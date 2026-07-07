# Approval & Governance — Known Gaps (Step 65H.2)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **[tracked, authorized-as-acceptable] Approval expired / timeout path not executed.** Read-only
   inspection found **no safe expiry/timeout route** in the approval-engine or the resume engine
   (no expire endpoint, no scheduled timeout job; `approval_requests` has no expiry column exercised
   by a safe path). Triggering an "expired" state would require DB time manipulation or faking
   expiry, which the operator explicitly **forbade**. Per the 65H.2 authorization, this is recorded
   as a **tracked gap**, not a failure. A future enhancement could add a safe approval-TTL /
   expiry mechanism (and an `expired` status) so this path can be validated non-destructively.
2. **[non-blocking, evidence nuance] `/operations/approval-decisions/{task_id}` is not the approval
   evidence surface.** It returns `count=0` for these workflows because it surfaces Stage-52 governed
   operator-action decisions, not the workflow approval path. Approval evidence is on the workflow
   state (`approval_status`) + `/audit-evidence` + the approval-engine request status. A future UI
   enhancement could add a dedicated approvals view.
3. ~~Operator UI validation pending.~~ **RESOLVED** — the operator confirmed **VISIBLE** on the
   formal Admin Console pages. See
   [approval-governance-operator-validation-request.md](approval-governance-operator-validation-request.md).

## Non-gaps (done)
- Approval **required / granted / denied** paths validated; **production-block** path validated;
  auto-resume on approval and terminal-on-reject confirmed; a production action was blocked and left
  unapproved; `production_executed_true_count=0`; no external integration used; ≤3 workflows.

## Blocking gaps
- **None.** No gap blocks the technical result; the expiry path is an authorized-acceptable tracked
  gap, and the only open item is the pending operator UI validation.

## Status
Step 65H.2: **PASS_WITH_GAPS**. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
