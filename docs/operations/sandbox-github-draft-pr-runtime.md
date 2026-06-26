# Sandbox GitHub — Draft PR Runtime (Step 59)

- SDK: `shared/sdk/sandbox_github/client.py` (`SandboxGitHubClient`), `store.py`
- API: `apps/orchestrator/src/sandbox_github_api.py`
- Migration: `migrations/025_sandbox_github_draft_pr.sql`
- Verifier: `scripts/verify_sandbox_github_draft_pr_runtime.py` → `SANDBOX_GITHUB_DRAFT_PR_RUNTIME_VERIFY`

## Flow
1. Operator authenticates (test-local auth + CSRF) and POSTs a request with a `reason`,
   a `repository_key` (never raw owner/repo), `project_id`, and `work_item_id`.
2. The work item / project are resolved for linkage. A `production_effect` work item is
   **blocked** (`production_effect_requires_approval`) — never a PR.
3. `SandboxGitHubClient.request_draft_pr` resolves the mode, validates against the
   policy / allowlist / branch / metadata models, and either:
   - **dry_run** → `planned` (a validated plan, no side effect), or
   - **live_sandbox** → creates a sandbox branch + a *draft* PR (only when enabled with a
     credential), else `blocked`.
4. The result is persisted to `sandbox_github_draft_prs` with full linkage
   (`project_id` / `project_key` / `work_item_id` / `work_item_key` / `correlation_id` /
   `repository_key` / `branch_name` / `draft_pr_url` / `draft_pr_number` / `mode` /
   `status` / `audit_event_id`) and an audit entry is written.

## Endpoints
- `POST /operations/github/sandbox-draft-pr` — controlled request (auth + CSRF + reason
  + audit). The only write endpoint.
- `GET  /operations/github/sandbox-draft-pr` and `.../requests` — list.
- `GET  /operations/github/sandbox-draft-pr/{request_id}` — detail.
- `GET  /operations/github/sandbox-draft-pr/policy | allowlist | safety | readiness`.

A draft PR record is **not** a merge, **not** a review, **not** a production approval.

## Live mode
`live_sandbox` requires `SANDBOX_GITHUB_LIVE=true` **and** `SANDBOX_GITHUB_TOKEN`. In the
test environment neither is configured, so live mode is blocked and only dry_run plans
are produced (`sandbox_github_draft_pr_created_count=0`). The orchestrator container does
not carry a token.
