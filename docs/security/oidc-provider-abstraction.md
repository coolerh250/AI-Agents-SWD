# OIDC Provider Abstraction (Step 52.2)

Status: **disabled / unconfigured — not deployed, not production-ready.**

This step adds a *model-only* OIDC provider abstraction. It defines the
interface, config schema, and contracts a future production identity step would
implement. It connects to **no** IdP, fetches **no** discovery document or JWKS,
exchanges **no** authorization code, validates **no** real token, and creates
**no** session.

## SDK

`shared/sdk/identity/`:

| Module | Purpose |
|---|---|
| `oidc_models.py` | Strict pydantic models. `SecretRef` carries no value; `client_secret` is expressible only as a reference. `enabled` / `production_allowed` default to `false`; `unknown_user_behavior` is constrained to `deny`. |
| `oidc_provider.py` | `OidcProvider` abstraction. Every live operation (discovery, JWKS, code exchange, token validation) raises `OidcDisabledError` in this step. |
| `oidc_config.py` | Read-only loader + fail-closed validator. Reports `disabled_unconfigured`, `disabled_missing_required_fields`, `invalid`, or `ready_for_future_enablement`. |
| `oidc_policy.py` | Loads the OIDC safety policy catalog. |
| `oidc_redaction.py` | Secret / token-shape detection (no network). |

The abstraction imports **no** HTTP client (`requests` / `httpx` / `aiohttp`),
which the combined verifier enforces.

## Config files

`infra/identity/`: `oidc-provider-catalog.yaml`,
`production-oidc-disabled-config.yaml`, `oidc-discovery-contract.yaml`,
`jwks-reference-model.yaml`, `oidc-claim-contract.yaml`,
`oidc-role-mapping-contract.yaml`, `oidc-callback-boundary.yaml`,
`oidc-state-nonce-pkce-contract.yaml`, `oidc-token-validation-boundary.yaml`,
`oidc-safety-policy-catalog.yaml`.

The committed provider `production-oidc-placeholder` is `enabled: false`,
`productionAllowed: false`, `configured: false`, `status:
disabled_unconfigured`, with empty issuer / client ID / client-secret ref /
redirect URIs and discovery/JWKS fetch disabled.

## What this step does NOT do

No real login, callback, code exchange, token parsing, refresh/access token,
JWKS or discovery fetch, real issuer / tenant / client ID / client secret,
external IdP connection, group→role mapping execution, production session
hardening, or Admin Console login UI. Those are deferred to Step 52.3 / 52.4 and
later. **No production identity readiness is declared.**

Verifier marker: `OIDC_PROVIDER_ABSTRACTION_VERIFY: PASS`.
