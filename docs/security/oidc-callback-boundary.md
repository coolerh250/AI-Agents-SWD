# OIDC Callback Boundary (Step 52.2)

`infra/identity/oidc-callback-boundary.yaml` is a **design** for a future OIDC
callback. No usable callback exists: the callback is disabled and would reject
all input. There is no authorization-code exchange, no token handling, and no
session creation in this step.

## Required (future) behaviour

* Authorization request must carry `state`, `nonce`, and PKCE (`S256`).
* The redirect URI must be on an allowlist.
* The callback must **reject**: provider disabled, missing/invalid `state`,
  invalid `nonce`, missing `code`, tokens in the URL fragment.
* The callback must **not**: log the authorization code or token, create a
  session before token validation passes, or assign a role before backend role
  mapping passes.
* Success and failure are audited **without** any raw token or code.

## Route policy

Only a read-only status surface (`GET /auth/oidc/status`, `handlesCode: false`)
is permitted. A code-handling `GET /auth/oidc/callback` route is explicitly
forbidden until token validation is implemented and verified
(`callback_disabled_until_token_validation_ready`).

See [oidc-token-validation-boundary.md](oidc-token-validation-boundary.md) and
the state/nonce/PKCE contract (`oidc-state-nonce-pkce-contract.yaml`).
