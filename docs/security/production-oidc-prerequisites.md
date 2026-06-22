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
