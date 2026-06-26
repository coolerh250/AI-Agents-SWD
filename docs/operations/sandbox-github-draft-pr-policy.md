# Sandbox GitHub Draft PR — Policy (Step 59)

- Model: `infra/github/sandbox-github-draft-pr-policy.yaml`
- SDK: `shared/sdk/sandbox_github/policy.py`
- Verifier: `scripts/verify_sandbox_github_policy.py` → `SANDBOX_GITHUB_POLICY_VERIFY`

Defines the controlled boundary for creating **draft** pull requests inside an
allowlisted sandbox repository. This is a **sandbox-only baseline** — NOT production
GitHub automation, NOT merge automation, NOT a real customer-repo flow.

## Modes
- `defaultMode: dry_run` — the request is validated and a plan is produced; **no side
  effect** (no branch, no PR, no external call).
- `live_sandbox` — creates a sandbox branch + a *draft* PR. Gated by an explicit env
  flag (`SANDBOX_GITHUB_LIVE=true`) **and** a credential (`SANDBOX_GITHUB_TOKEN`). With
  no credential the request is **blocked** — never a fabricated live success.

## Dangerous toggles (all false)
`allowMerge`, `allowReadyForReview`, `allowNonSandboxRepo`, `allowProductionBranch`,
`allowWorkflowDispatch`, `allowIssueWrite`, `allowReleaseWrite`, `allowDeploymentWrite`.
These read straight from the committed YAML so they cannot silently drift true in code.

## Invariants
- A `production_effect` work item is never turned into a PR (it is blocked /
  routed to human approval).
- `production` / `release` / `hotfix` are never valid base branches.
- `productionReady: false` always.
