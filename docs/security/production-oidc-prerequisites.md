# Production OIDC Prerequisites (Step 52.1 / Stage 54A)

**Requirements only — no real IdP, no issuer, no client, no discovery, no login.**
Source: [production-oidc-prerequisites.yaml](../../infra/identity/production-oidc-prerequisites.yaml).

Required-but-**unconfigured**: issuer URL, JWKS URI, client id, client secret
(production secret store), redirect URIs, `groups` claim, group→role mapping,
production session secret store, logout, audit subject mapping. Unknown-user
behavior: **deny**; default role: **none**.

Status: OIDC **not configured**, no discovery performed, no real issuer/client/
secret, no production login. Deferred — provider abstraction (52.2), role mapping
+ session hardening (52.3), production secret store (53).

## Update — Step 52.2 (Stage 54B)

The provider abstraction is now in place but remains **disabled and
unconfigured**. See [oidc-provider-abstraction.md](oidc-provider-abstraction.md)
and [oidc-disabled-production-config.md](oidc-disabled-production-config.md).
All prerequisites above are still unconfigured; no discovery or JWKS fetch was
performed; production OIDC is not ready. Role mapping + session hardening remain
deferred to 52.3, production secret store to 53.

**Step 53 (Stage 55A):** the OIDC client secret is now catalogued as a critical
secret with a reference (`store=disabled`, `configured=false`) in the secret
management foundation ([secret-inventory.md](secret-inventory.md),
[secret-management-foundation.md](secret-management-foundation.md)). The client
secret can only ever be a `SecretRef`; no real value is set and no production
secret store is connected.
