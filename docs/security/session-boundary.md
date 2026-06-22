# Session Boundary (Step 52.1 / Stage 54A)

Source: [session-inventory.yaml](../../infra/identity/session-inventory.yaml);
`shared/sdk/operator_actions/session.py`.

* HMAC-SHA256 signed token `base64url(identity|issued|expires).sig`; **only
  `sha256(token)` is persisted** (a leaked DB row cannot reconstruct a cookie).
* Cookie: `HttpOnly`, `SameSite=strict`, `Secure` configurable, max-age 30 min.
* Signing secret from a runtime key file or ephemeral in-memory (test); **never
  committed/logged/returned**. Production secret store **not configured**.
* Confirmation nonce hashed at rest (raw returned once). CSRF token recomputed,
  never persisted.
* Revocation supported (logout); expiry backend-enforced.

**Gaps (deferred to 52.3):** periodic session cleanup job, concurrent-session
cap, global forced-logout / key-rotation revocation sweep, production secret
store + key rotation.
