# Sandbox GitHub — Repository Allowlist (Step 59)

- Model: `infra/github/sandbox-repository-allowlist.yaml`
- SDK: `shared/sdk/sandbox_github/allowlist.py`
- Verifier: `scripts/verify_sandbox_github_allowlist.py` → `SANDBOX_GITHUB_ALLOWLIST_VERIFY`

A request never names an arbitrary owner/repo: it carries a repository **key** that must
resolve to an entry here. An unknown key, a disallowed base branch, or a head branch that
does not match the allowed prefix is rejected — arbitrary owner/repo is impossible.

## Entry fields
`key`, `owner`, `repo`, `allowed`, `sandboxOnly`, `allowedBaseBranches`,
`allowedHeadPrefix`, `allowDraftPR`, and the always-false `allowMerge` /
`allowReadyForReview` / `allowRelease` / `allowDeployment` / `allowWorkflowDispatch`.

## Rules
- `repositoryKeyOnly` — the request carries a key, never raw owner/repo.
- `noArbitraryRepo` / `noArbitraryOwner` / `noProductionRepoWildcard`.
- `rejectRepoNotInAllowlist`, `draftPrOnly`, `baseBranchMustBeAllowed`,
  `headBranchMustMatchAllowedPrefix`.

Only sandbox repositories are listed. Production / customer repositories and wildcards are
never permitted. `resolve_repository(key)` returns `None` unless the entry is
`allowed` **and** `sandboxOnly`.
