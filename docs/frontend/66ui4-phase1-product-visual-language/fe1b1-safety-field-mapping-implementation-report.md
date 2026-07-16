# FE.1B.1 Safety Field Mapping Calibration - Frontend Implementation Report

Marker: `STEP66UI4_FE1B1_MAPPING_CALIBRATION_VERIFY: PASS`

## Result

The Calm Safety Posture now derives global automation posture only from the existing global fields
`task_api_workflow_dispatch_enabled` and `task_workroom_resume_dispatch_enabled`. The absence of
task/workroom/workflow-scoped fields no longer makes the global badge Unavailable.

This is frontend mapping calibration only. Existing `/operations/safety` data only is used. The
endpoint, response shape, API client, backend, database, workflow, infrastructure, production
behavior, and external integrations are unchanged.

## Mapping changes

- Removed `dispatch_enabled` and `resume_dispatch_enabled` from global automation truth.
- Removed `approval_required` and `requires_approval` from global tone computation.
- Replaced the global approval fact with: `Approvals are tracked per task. Review task details for
  approval requirements.`
- Kept the four retired field names in the expandable evidence disclosure as endpoint scope notes,
  each labeled `Not applicable at this endpoint`.
- Did not use `work_item_dispatch_enabled` or any similarly named substitute.

## Conservative fallback

Safe is shown only when all actual required global evidence is present and safe:

- both production action counts are numeric zero;
- both task/workroom workflow dispatch flags are boolean false;
- all three external action flags are boolean false;
- production delegation is boolean false; and
- endpoint `result` is `safe`.

An enabled risk, positive production count, or non-safe endpoint result produces Attention. Missing
or incorrectly typed actual global evidence produces Unavailable. The implementation does not fake
Safe and does not treat missing values as false.

## Evidence handling

Raw safety evidence remains accessible through `Evidence / details` in both compact and full modes.
Actual tracked endpoint values are displayed as returned. Retired task/workroom/workflow-scoped
fields are retained only to explain endpoint applicability and are never presented as missing global
evidence.

## Tests

The realistic sanitized fixture matches the confirmed global schema and intentionally omits
`dispatch_enabled`, `resume_dispatch_enabled`, `approval_required`, and `requires_approval`. Tests
cover Safe, each automation flag enabled, positive production count, each external action enabled,
missing endpoint result, missing production delegation evidence, per-task approval wording, raw
evidence access, endpoint-applicability labels, and compact mode.

Final command results are recorded in
`docs/test/step66ui4-fe1b1-safety-field-mapping-test-report.md`.

## Scope statement

Codex authorization limited to FE.1B.1. FE.1C/FE.1D not started. No backend change. No API change.
No database change. No workflow change. No `/operations/safety` response shape change. No new
endpoint. No workflow dispatch or resume. No production action. No external action. Raw safety
evidence remains accessible. Product Owner validation, merge, and deployment remain separate gates.

No /operations/safety response shape change was made.
