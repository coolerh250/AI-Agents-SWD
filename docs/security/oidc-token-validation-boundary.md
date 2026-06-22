# OIDC Token Validation Boundary (Step 52.2)

`infra/identity/oidc-token-validation-boundary.yaml` is a **design** for future
ID-token validation. No real token is validated, parsed, or persisted in this
step; validation is disabled until a provider is configured.

## Required (future) checks

* Issuer must match the configured issuer.
* Audience must match the client ID.
* `exp` and `iat` required; `nonce` required; signature required; `kid`
  required; JWKS key rotation required.

## Algorithm policy

* Allowed: `RS256`.
* Rejected: `none` (always), `HS256` (not valid for an external IdP's ID token —
  a symmetric secret cannot authenticate the provider).

## Token handling

* Raw token is **never** audited.
* Raw token is **never** persisted.

Clock-skew tolerance is a future configuration item. Status:
`disabled_until_provider_configured`.
