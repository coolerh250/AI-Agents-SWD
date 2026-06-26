# Sandbox GitHub — Draft PR Verification (Step 59)

Combined: `scripts/verify_sandbox_github_draft_pr_baseline.sh`
→ `SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY: PASS | BLOCKED | FAIL`

It chains the Step 58 combined (which dedupes Step 52–57 + the tenant strategy note + the
6 metrics verifiers), then runs the 9 Step 59 verifiers, the targeted tests, and the
safety posture check.

| Verifier | Marker |
| --- | --- |
| Policy | `SANDBOX_GITHUB_POLICY_VERIFY` |
| Allowlist | `SANDBOX_GITHUB_ALLOWLIST_VERIFY` |
| Branch policy | `SANDBOX_GITHUB_BRANCH_POLICY_VERIFY` |
| PR metadata | `SANDBOX_GITHUB_PR_METADATA_VERIFY` |
| Client | `SANDBOX_GITHUB_CLIENT_VERIFY` |
| Draft PR runtime (live) | `SANDBOX_GITHUB_DRAFT_PR_RUNTIME_VERIFY` |
| Operations visibility (live) | `SANDBOX_GITHUB_OPERATIONS_VISIBILITY_VERIFY` |
| Admin Console | `ADMIN_CONSOLE_SANDBOX_GITHUB_VERIFY` |
| Safety fields (live) | `SANDBOX_GITHUB_SAFETY_FIELDS_VERIFY` |

## Targeted tests (0 skipped)
`tests/test_sandbox_github_{policy,allowlist,branch_policy,pr_metadata,client,dry_run,
runtime,operations_api,operations_read_only,safety_fields,no_production_actions}.py` and
`tests/test_admin_console_sandbox_github.py`.

## A verifier FAILs if
arbitrary repo accepted · non-sandbox write · production branch · merge / ready-for-review
/ workflow dispatch / release / deployment enabled · token exposed or committed · Admin
Console exposes a token input or a merge / ready-for-review / workflow-dispatch /
production-deploy control · a `production_effect` work item creates a PR · ArgoCD sync ·
Kubernetes mutation · external send · production action · `production_executed_true_count != 0`.

## Run
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  bash scripts/verify_sandbox_github_draft_pr_baseline.sh
```
