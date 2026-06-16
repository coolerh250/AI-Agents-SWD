# Admin Console Auth & Session (Stage 52)

## Auth modes

- `test_local_signed_session` — validation/test only. A signed session token
  (HMAC-SHA256) is issued by `POST /operations/admin-console/auth/test-login`
  and stored as an **HttpOnly**, **SameSite=Strict** cookie
  (`admin_console_session`). `Secure` is configurable
  (`ADMIN_CONSOLE_COOKIE_SECURE`, false for test HTTP; production requires true).
- `oidc` — production, **required but unconfigured** (disabled this stage).
- `disabled` / unknown — **fail closed**; operator actions disabled, no
  anonymous action.

Env (validation server): `ADMIN_CONSOLE_AUTH_MODE=test_local_signed_session`,
`ADMIN_CONSOLE_TEST_AUTH_ENABLED=true`,
`ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED=false`, `ADMIN_CONSOLE_OIDC_ENABLED=false`,
`ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS=true`. Test auth can activate **only** in
`test_local` mode with production auth disabled.

## Session security

- Signing secret resolved from a runtime key file
  (`ADMIN_CONSOLE_SESSION_KEY_FILE` or `.runtime/admin-console-session-key`,
  gitignored) or an ephemeral in-process secret; never committed, never logged,
  never returned in a response body.
- The DB stores only `session_hash = sha256(token)` — a leaked row cannot
  reconstruct a cookie.
- Short expiry (30 minutes). Expired / revoked sessions are rejected.
- The session token lives only in the HttpOnly cookie; it is never placed in
  `localStorage` or a URL query string.

## Endpoints

`POST /auth/test-login` (test only), `POST /auth/logout` (revokes),
`GET /auth/session`, `GET /auth/csrf`. CSRF tokens are HMAC-bound to the session
hash and echoed in `X-CSRF-Token` on every mutation.

## Test login

Only when `ADMIN_CONSOLE_TEST_AUTH_ENABLED=true` in `test_local` mode. Uses a
fixed non-sensitive identity (`operator-test`); no hardcoded production
password; the response never returns the signing secret. There is no usable
fallback credential in production mode.
