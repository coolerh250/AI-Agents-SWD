# Product Owner UI Validation Record — Step 66UI.4-FE.1B.1 Safety Field Mapping Calibration

> **Validation record only. No runtime code changed by this document. No backend changed. No
> frontend runtime changed. No database changed. No workflow executed. No external action. No
> production action. PR not merged by this document.**

Recorded by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), following the Step 66UI.4-FE.1B.1-VP temporary
test-runtime deployment of `frontend/66ui4-fe1b1-safety-field-mapping` (Draft PR #9, commit
`974822d`) for UI validation. The temporary deployment was a static-file-only swap of the Admin
Console bundle inside the already running orchestrator container (no image rebuild, no restart, no
backend/API/database/workflow change), authorized explicitly: "授權 Claude Code 將 PR #9
frontend/66ui4-fe1b1-safety-field-mapping 部署到 test runtime 供 FE.1B.1 UI validation；不 merge
main；不授權 FE.1C/FE.1D implementation。"

## Product Owner response (verbatim)

```text
都可以看見，確認無誤
```

## Interpretation

```text
Step 66UI.4-FE.1B.1 Product Owner UI Validation: VISIBLE
No blocking gap.
```

## Clarification during validation

During validation, the Product Owner asked "找不到 approval 文案為 per-task" (could not find the
per-task approval wording). This was investigated live rather than assumed:

**Root cause (confirmed by source inspection, not merely code reasoning):** `CalmSafetyPosture`'s
human-readable `facts` array — which contains the per-task approval sentence ("Approvals are
tracked per task. Review task details for approval requirements.") — is only rendered when
`compact` is falsy:

```text
{!compact && (
  <ul className="calm-safety-facts" aria-label="Safety facts">
    {posture.facts.map((fact) => (<li key={fact}>{fact}</li>))}
  </ul>
)}
```

The persistent top bar (`SafetyStatusBar.tsx`) renders `<CalmSafetyPosture data={state.data}
compact />` — so the facts list, including the per-task approval sentence, is never shown there by
design. Only the Safety Center page (`SafetyCenter.tsx`) renders the full, non-compact panel that
includes it.

**Not a regression introduced by PR #9.** `SafetyStatusBar.tsx` and `SafetyCenter.tsx` are both
untouched by this PR's diff; this `compact`-vs-full split has been unchanged since the original
FE.1B implementation.

**Resolution.** The Product Owner was directed to the Safety Center page to see the per-task
approval sentence there, in addition to the top bar's badge/title/raw-evidence view. After checking
both locations, the Product Owner confirmed both are correct as-is.

## Validation result recorded

1. **Safety badge state.** Resolves to **Safe** (the accepted Step 66UI.4-FE.1B-V "Unavailable" gap
   is resolved by this deployment) — confirmed by the Product Owner and independently confirmed
   beforehand in Step 66UI.4-FE.1B.1-VP by executing the actual compiled mapping logic against the
   live `/operations/safety` payload.
2. **Per-task approval wording.** Visible on the Safety Center full panel; intentionally not
   rendered in the compact top bar (pre-existing, unchanged split). Confirmed acceptable by the
   Product Owner after checking both locations.
3. **Raw evidence/details.** Confirmed accessible in both compact (top bar) and full (Safety
   Center) views.
4. **Retired fields.** Confirmed labeled "Not applicable at this endpoint" rather than treated as
   missing risk.
5. **Scope preserved.** The Product Owner's verdict was given against a deployment confirmed,
   before and during validation, to contain only the reviewed FE.1B.1 diff (no FE.1C/FE.1D content)
   — see Step 66UI.4-FE.1B.1-R and Step 66UI.4-FE.1B.1-VP.

## Gap status

```text
Step 66UI.4-FE.1B-V accepted gap (Safety badge showing Unavailable instead of Safe): RESOLVED by
  this deployment, confirmed by the Product Owner.

No new blocking gap from this validation pass.

Carried forward, non-blocking (unrelated to this stage, not newly raised here):
- Platform Ops comfortable-vs-compact table density distinction not yet implemented (carried from
  FE.1A).
- Safety Center's legacy raw KeyValueTable summary remains alongside the new calm panel (carried
  from FE.1B-R review).
- The compact top bar does not surface the human-language facts list (including the per-task
  approval sentence); only the full Safety Center panel does. Confirmed acceptable by the Product
  Owner in this validation, not treated as blocking.
```

## Safety posture during validation

```text
production_executed_true_count: 0 (before, during, and confirmed after deployment)
/operations/safety result: "safe" throughout
Workflow dispatch: not triggered
Workflow resume: not triggered
Production action: not triggered
External action: not triggered
Containers: 28, all Up, unchanged
```

## Merge status

```text
Merge readiness from Product Owner validation perspective: ready, gap resolved, no blocking issue
Actual merge authorization: not yet granted in this step
Explicit merge authorization still required
FE.1C / FE.1D: still not authorized
```

This document does not merge `frontend/66ui4-fe1b1-safety-field-mapping` (PR #9) and does not grant
merge authorization. Per `docs/process/operator-validation-standard.md` and
`.agents/skills/stage-gate/SKILL.md` (Product Owner Validation Gate, Merge Gate), only the Product
Owner grants merge authorization, and only as an explicit, separate act.

## Deployment disposition

The temporary test-runtime deployment remains live as of this record (not rolled back) — it was not
merged to `main` and required no repository change to deploy. A pre-deployment bundle backup
remains available on the test host for immediate rollback if requested.

## Statement

Validation record only. No runtime code changed. No backend changed. No frontend runtime changed.
No database changed. No workflow executed. No external action. No production action. PR not
merged.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
