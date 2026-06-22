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

## Update — Step 52.3 (Stage 54C)

The session hardening model + a non-destructive cleanup utility now exist; see
[session-hardening-model.md](session-hardening-model.md),
[session-concurrency-policy.md](session-concurrency-policy.md),
[forced-logout-model.md](forced-logout-model.md), and
[session-key-rotation-model.md](session-key-rotation-model.md). Status: cleanup
implemented (dry-run default, never deletes, no raw token); concurrency
recorded-not-enforced; forced logout server-authoritative at session level
(user/role-change modelled); key rotation **model only**. Idle timeout,
concurrency enforcement, and the production secret store / key rotation backend
(Step 53) remain required before production. Raw token still never persisted.
