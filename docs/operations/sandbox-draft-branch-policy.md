# Sandbox GitHub — Draft Branch Naming Policy (Step 59)

- Model: `infra/github/sandbox-draft-branch-policy.yaml`
- SDK: `shared/sdk/sandbox_github/branch.py`
- Verifier: `scripts/verify_sandbox_github_branch_policy.py` → `SANDBOX_GITHUB_BRANCH_POLICY_VERIFY`

Branches are deterministically generated from sanitized inputs:

```
sandbox/ai-agents/{project_key}/{work_item_key}/{short_correlation_id}
```

## Sanitization
Each segment is lowercased and any run of characters outside `[a-z0-9-]` collapses to a
single `-`, then repeated/leading/trailing dashes are stripped. This inherently removes
spaces, path-traversal (`..`), and shell metacharacters.

## Guarantees (validated by `validate_branch_name`)
- Must start with `sandbox/ai-agents/`.
- No `..`, no spaces, no `; | & $ \` ( ) < > \\`.
- Never `main` / `master` / `production` / `release` / `hotfix`.
- First segment after the prefix is never a `production` / `release` / `hotfix` prefix.
- Bounded length (`maxLength`); collision handling is deterministic (the short
  correlation id suffix).
