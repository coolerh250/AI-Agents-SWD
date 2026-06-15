# Delivery Readiness Model (Stage 49)

`delivery_readiness_snapshots` captures a compact, Admin-Console-friendly view
of whether a delivery package is ready for human operator review.

## Readiness fields

| Field | Meaning |
|---|---|
| `project_ready` | a project brief exists |
| `design_ready` | design review exists with 0 blocking findings |
| `workspace_ready` | controlled workspace generated files |
| `qa_ready` | QA `passed` / `passed_with_findings` |
| `acceptance_ready` | acceptance criteria evaluated, 0 failed |
| `safety_ready` | safety `safe` / `safe_with_findings` |
| `docs_ready` | all package sections present (0 missing) |
| `human_acceptance_pending` | always `true` this stage |
| `blocking_reasons` | list of unmet technical readiness reasons |
| `warnings` | non-blocking notes (e.g. missing sections, gate warnings) |

## `ready_for_operator_review` logic

`readiness_status = ready_for_operator_review` when **all** technical readiness
flags are true (`project`, `design`, `workspace`, `qa`, `acceptance`, `safety`)
and the acceptance gate resolved to `passed` / `passed_with_findings`. Human
acceptance is still pending.

## `blocked` logic

`readiness_status = blocked` when the acceptance gate is `blocked` / `failed`
(a blocking technical / safety / governance check failed, tests failed,
acceptance failed, or safety is not safe). The unmet flags appear in
`blocking_reasons`.

## `failed` logic

Reserved for an unrecoverable build error (the package itself could not be
built). The build path persists a `failed` / `blocked` package shell so the
failure is inspectable.

## Admin Console v0 usage

Admin Console v0 (Step 48, read-only) will read:

- `/operations/safety` → `delivery_package_ready_for_admin_console`,
  `latest_delivery_readiness_status`, `latest_human_acceptance_status`.
- `/operations/delivery-packages/{id}/readiness` for the per-package snapshot.

`delivery_package_ready_for_admin_console=true` requires: package
`ready_for_review`, gate `passed` / `passed_with_findings` with decision
`ready_for_operator_review` / `controlled_only_complete`, human acceptance
`pending`, and readiness `ready_for_operator_review`.
