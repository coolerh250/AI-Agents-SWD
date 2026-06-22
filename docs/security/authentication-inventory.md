# Authentication Inventory (Step 52.1 / Stage 54A)

Inventory + boundary model only. **No real OIDC, no production auth, no external
IdP.** test-local auth is non-production. Source:
[authentication-inventory.yaml](../../infra/identity/authentication-inventory.yaml).

## Modes

| Mode | Status | Environments | Production allowed |
| --- | --- | --- | --- |
| `test_local_signed_session` | active (test) | dev, test | **no** |
| `oidc` | required-but-unconfigured, disabled | staging/prod (future) | **no** |
| `disabled` | fail-closed default / unknown mode | all | **no** |

## Verified behaviors

* Anonymous blocked (no cookie → 401); logout revokes session + deletes cookie.
* Session expiry enforced (30 min); revoked/expired sessions rejected.
* Cookie `HttpOnly`, `SameSite=strict`, `Secure` configurable (must be true in prod).
* Token in an HttpOnly cookie — **never** localStorage, never in a URL.
* Production auth fail-closed: `resolve_auth_config` disables operator actions for
  unknown modes and for production mode without an OIDC-ready config; test auth is
  forced off unless `test_local` mode with production auth disabled.

## Production readiness

`not_production_ready`: production OIDC not configured, production session secret
store absent, cookie Secure not enforced, no group→role mapping. Deferred to
Step 52.2/52.3/53. This stage declares **no** production identity readiness.
