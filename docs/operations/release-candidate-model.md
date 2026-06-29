# Release Governance — Release Candidate Model (Step 60)

- Model: `infra/release/release-candidate-model.yaml`
- SDK: `shared/sdk/release_governance/candidates.py`, `models.py`
- Verifier: `scripts/verify_release_candidate_model.py` → `RELEASE_CANDIDATE_MODEL_VERIFY`

A release candidate aggregates delivery / work-item / sandbox-draft-PR evidence into a
governance object. It is **not** a release, **not** a merge, **not** a production
approval.

## Fields
`release_candidate_id`, `project_id`, `work_item_ids`, `delivery_package_ids`,
`sandbox_draft_pr_ids`, `version_label`, `target_environment`, `status`,
`readiness_status`, `security_status`, `runtime_status`, `gitops_status`,
`approval_status`, `production_ready`, `created_at`, `updated_at`.

## Statuses
`draft`, `evidence_collecting`, `ready_for_operator_review`, `blocked`, `rejected`,
`accepted_nonproduction`, `archived`.

## Invariants
- `target_environment` defaults to `nonprod` and can never be `production` (DB CHECK +
  policy validation).
- `production_ready` is always false.
- `accepted_nonproduction` is **not** a production approval.
- A sandbox draft PR is not a merge; a release candidate is not a release.
