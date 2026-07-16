# Step 66UI.4-FE.1B.1-P — Safety Field Mapping Calibration Planning Record

Marker: `STEP66UI4_FE1B1_PLANNING_VERIFY: PASS`

Planning only. No runtime code changed. Codex not authorized. FE.1C/FE.1D remain unauthorized.

## Accepted gap referenced

```text
Safety badge currently displays "Unavailable" rather than "Safe" because the real
/operations/safety response is missing these expected fields:
- dispatch_enabled
- resume_dispatch_enabled
- approval_required
- requires_approval

This is an accepted, non-blocking Product Owner validation gap.
```

## Method

Live `/operations/safety` response on the test runtime (main at merge commit `5a2bc4e`) inspected via
sanitized field-presence/type checks (no raw payload, secret, or infrastructure identifier
reproduced). `CalmSafetyPosture.tsx`'s mapping logic re-read in full. Backend source
(`task_api.py`, `workroom_api.py`, `workflow.py`, `workflow_events.py`, `resume_engine.py`,
`operations.py`, `shared/sdk/work_items/safety.py`) traced to confirm where each of the four
"missing" fields actually exists.

## Root cause confirmed

All four fields are genuine fields of *other* endpoints (per-task `/tasks`, per-workroom-message
`/tasks/{id}/workroom`, per-workflow `/operations/workflows`), not of `/operations/safety` — a
category/scope error inherited from the pre-FE.1A `SafetyStatusBar.tsx`'s original field list, not a
genuine data-availability gap. Full detail in
`docs/frontend/66ui4-phase1-product-visual-language/fe1b1-safety-field-mapping-plan.md` §3.

## Cautionary finding

A similarly-named live field, `work_item_dispatch_enabled` (`true`), was traced to
`shared/sdk/work_items/safety.py` and found to be a feature-enabled flag ("the work-item dispatch
subsystem exists"), not a risk flag — confirming it would have been an incorrect substitute for the
missing `dispatch_enabled` had one been chosen by name-similarity alone. Recorded as a hard rule for
future calibration work: confirm semantics against source before wiring up any field.

## Recommended calibration (not implemented in this stage)

```text
1. Remove dispatch_enabled/resume_dispatch_enabled from AUTOMATION_FIELDS; rely on the
   already-present task_api_workflow_dispatch_enabled + task_workroom_resume_dispatch_enabled.
2. Remove the global "Approval requirement" fact/fields; replace with an honestly-scoped per-task
   note.
3. Relabel or remove the four retired rows in the raw-evidence disclosure ("Not applicable at this
   endpoint," never "not reported").
4. No backend/API/database/workflow change; no /operations/safety response shape change.
```

Once applied, `getCalmSafetyPosture()` would correctly compute tone "safe" against the live payload
confirmed in this stage, without overclaiming and without any backend change.

## No runtime files changed

Confirmed — this stage's diff is confined to `docs/frontend/66ui4-phase1-product-visual-language/**`,
`docs/contracts/66ui4-fe1b1-safety-field-mapping/**`, `docs/stages/66ui4-fe1b1/**`, `docs/test/**`,
`source/progress.md`, and this stage's own verifier/test — no `apps/**` path.

## Verdict

Planning complete. Codex FE.1B.1 implementation not authorized by this record — requires a separate,
explicit Product Owner authorization following acceptance of this plan.

## Statement

Planning document only. No runtime code changed. No backend/API/database/workflow change.
`/operations/safety` response shape unchanged. No production/external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
