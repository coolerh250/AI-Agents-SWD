# Product Owner UI Validation Record — Step 66UI.4-FE.1B Calm Safety Posture

> **Validation record only. No runtime code changed by this document. No backend changed. No
> frontend runtime changed. No database changed. No workflow executed. No external action. No
> production action. PR not merged by this document.**

Recorded by: Claude Code (Lead Engineer / Architecture Owner — see
`docs/process/role-responsibility-matrix.md`), following a temporary test-runtime deployment of
`frontend/66ui4-fe1b-calm-safety` (PR #7, commit `6cf8efe`) for UI validation. The temporary
deployment was a static-file-only swap of the Admin Console bundle inside the already running
orchestrator container (no image rebuild, no restart, no backend/API/database/workflow change),
authorized explicitly: "授權 Claude Code 將 PR #7 frontend/66ui4-fe1b-calm-safety 部署到 test runtime 供
FE.1B UI validation；不 merge main；不授權 FE.1C/FE.1D。"

## Product Owner response (verbatim)

```text
VISIBLE
```

## Interpretation

```text
Step 66UI.4-FE.1B Product Owner UI Validation: VISIBLE
Accepted gap: safety indicator shows "Unavailable" instead of "Safe" due to a real backend/
  frontend field-name mismatch (see "Gap discovered during validation" below)
Blocking gap: none
```

Like the prior Step 66UI.2-FE.1 validation, this response carries one accepted, non-blocking gap —
raised by the Product Owner during the validation session itself, diagnosed live, and explicitly
accepted rather than treated as blocking.

## Gap discovered during validation

During validation, the Product Owner observed the global safety bar showing an **"Unavailable"**
posture badge (with the title "Safety status unavailable - check system evidence.") instead of the
expected "Safe" state, and asked whether this was correct.

**Root cause (confirmed live, not merely code-reasoned):** the real `/operations/safety` response on
the test runtime does not include four fields the `CalmSafetyPosture` component's safe/attention
mapping depends on: `dispatch_enabled`, `resume_dispatch_enabled`, `approval_required`,
`requires_approval` — confirmed absent by directly inspecting the live JSON payload (not merely
assumed). Because `getCalmSafetyPosture()` requires *all* automation fields to be explicitly `false`
before it will show "Safe" (and treats a missing/null field the same as "unknown," never as
implicitly `false`), the missing fields correctly and conservatively fall through to the
`"unavailable"` tone rather than fabricating "Safe."

**This is not a new defect introduced by FE.1B** — the same field names were already assumed by the
prior raw-dump `SafetyStatusBar.tsx` (`SAFETY_FIELDS` included the identical four names) and were
already silently rendered as "not reported" line items before this stage; the mismatch pre-dates
FE.1B. What FE.1B changes is the *consequence* of that pre-existing mismatch: instead of one quiet
"not reported" item buried in a flat list, the missing fields now suppress the entire calm summary
badge from ever reaching "Safe" in the current environment.

**Not a safety violation.** The conservative fallback is exactly the behavior
`calm-safety-posture-spec.md` and the FE.1B-R review required: never claim "safe" on missing/unknown
data. `production_executed_true_count` and the safety endpoint's overall `result` field were both
confirmed `0` / `"safe"` throughout — nothing was misreported as unsafe or hidden.

**Review-process note.** This gap was not caught during Step 66UI.4-FE.1B-R. That review verified the
safety-mapping logic by code reading and by re-running Codex's unit tests, which use synthetic
fixtures where all twelve fields are present — it did not independently query the live
`/operations/safety` payload to confirm the assumed field set actually exists on the running backend.
That live-data check is what surfaced this gap during Product Owner validation instead.

## Product Owner decision on this gap

```text
Accept as a known, non-blocking gap for now.
FE.1B remains deployed as-is; no rollback.
No remediation authorized in this stage.
A future authorized remediation stage may update the CalmSafetyPosture field mapping to match the
  fields the live backend actually returns.
```

## Validation result recorded

1. **Calm safety summary tone/copy** — visible and rendered; reassurance-first language confirmed
   present where data allows it.
2. **Safety facts + Evidence/details disclosure** — visible and rendered on Safety Center; raw field
   names and values confirmed present in the expandable detail, matching the FE.1B-R review's
   findings.
3. **Unavailable-state honesty** — confirmed live: when required fields are missing, the UI shows
   "Unavailable" rather than a fabricated "Safe," exactly as designed — the gap above is a UX/
   product-value shortfall in the current environment, not a safety-correctness failure.
4. **Scope preserved** — the Product Owner's `VISIBLE` verdict was given against a deployment
   confirmed, before and during validation, to contain only the reviewed FE.1B diff (no FE.1C
   Overview restructure, no FE.1D navigation polish) — see Step 66UI.4-FE.1B-R.

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

## Deployment method (for the record)

```text
1. Built frontend/66ui4-fe1b-calm-safety (commit 6cf8efe) in an isolated git clone on the test
   host (never touching the host's main repo clone), fetched directly from the GitHub origin URL.
2. Backed up the pre-existing dist bundle from the running orchestrator container.
3. Removed the prior deployment's asset files, then docker cp'd the new build into the running
   container's admin_console_static/dist/ (no image rebuild, no container restart).
4. Confirmed no orphaned old-hash asset files remained and that index.html referenced only the new
   hashes (index-D3ONvmz8.js / index-DcSljMgU.css -- deterministic, matching Claude Code's own local
   review-stage build of the same commit).
5. Verified admin console load (200), health endpoint, and the safety payload
   (production_executed_true_count: 0, result: safe) before providing the Product Owner an access
   tunnel.
```

## Gap status

```text
One accepted, non-blocking gap from this validation pass (see above) -- safety indicator shows
  "Unavailable" instead of "Safe" due to a live backend/frontend field-name mismatch; explicitly
  accepted by the Product Owner, not blocking.

Carried forward from Step 66UI.4-FE.1B-R review (technical, non-blocking, not newly raised here):
- Review checklist's illustrative safety field names differed from the server's actual field names
  (partially the same underlying issue now confirmed live).
- Codex's own verifier's scope check is a no-op on a clean checkout.
- Safety Center's legacy raw KeyValueTable summary remains alongside the new calm panel.
```

## Merge status

```text
Merge readiness from Product Owner validation perspective: ready, with the accepted gap noted
Actual merge authorization: not yet granted in this step
Explicit merge authorization still required
FE.1C / FE.1D: still not authorized
```

This document does not merge `frontend/66ui4-fe1b-calm-safety` (PR #7) and does not grant merge
authorization. Per `docs/process/operator-validation-standard.md` and
`.agents/skills/stage-gate/SKILL.md` (Product Owner Validation Gate, Merge Gate), only the Product
Owner grants merge authorization, and only as an explicit, separate act.

## Deployment disposition

The temporary test-runtime deployment remains live as of this record (not rolled back) — it was not
merged to `main` and required no repository change to deploy. A pre-deployment bundle backup remains
available on the test host for immediate rollback if requested.

## Statement

Validation record only. No runtime code changed. No backend changed. No frontend runtime changed.
No database changed. No workflow executed. No external action. No production action. PR not merged.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
