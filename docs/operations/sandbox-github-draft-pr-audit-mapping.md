# Sandbox GitHub — Draft PR Audit Mapping (Step 59)

- Model: `infra/github/sandbox-draft-pr-audit-mapping.yaml`
- SDK: `shared/sdk/sandbox_github/audit.py`

Every sandbox draft-PR operation emits an audit event. The orchestrator write endpoint
additionally records an operator-action audit entry (reusing the Step 52 audit chain).

## Events
- `sandbox_github_draft_pr_requested`
- `sandbox_github_draft_pr_policy_checked`
- `sandbox_github_draft_branch_created` (live_sandbox only)
- `sandbox_github_draft_pr_created` (live_sandbox only)
- `sandbox_github_draft_pr_blocked`
- `sandbox_github_draft_pr_failed`

## Required metadata
`actor`, `role`, `reason`, `project_id`, `work_item_id`, `repository_key`, `mode`,
`correlation_id`, and `production_executed` (always `false`).

## Forbidden metadata
`token`, `secret`, `raw prompt`, `chain-of-thought` — stripped by
`shared/sdk/sandbox_github/redaction.py` before the metadata leaves the SDK.
