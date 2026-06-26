# Sandbox GitHub — Credential Boundary (Step 59)

- Model: `infra/github/sandbox-github-credential-boundary.yaml`
- SDK: `shared/sdk/sandbox_github/policy.py` (`has_credential`, `TOKEN_ENV`),
  `shared/sdk/sandbox_github/client.py` (token read at call time only)

The sandbox draft-PR flow may obtain a token from an **environment variable or secret
reference only** (`SANDBOX_GITHUB_TOKEN`). The token is:

- **never committed** — it lives only in the environment / secret store.
- **never logged** — the SDK redacts forbidden keys/shapes before anything leaves it.
- **never returned** — no API response or Admin Console view carries it.

When the token is absent, `live_sandbox` is **blocked** (`live_sandbox_no_credential`);
the flow stays in dry_run / blocked and never fabricates a live success.

## Expected minimum scope
`repo:contents:write` (create sandbox branch) + `pull_requests:write` (open draft PR),
scoped to the sandbox repo only.

## Forbidden scope
`admin`, `workflow`, `deployment`, `production` — never requested.
