# Test vs Production Auth Boundary (Step 52.1 / Stage 54A)

Source: [auth-boundary-policy.yaml](../../infra/identity/auth-boundary-policy.yaml);
`shared/sdk/operator_actions/auth.py`.

## test-local signed session
dev/test only · controlled testing · may mint viewer/reviewer/operator/
platform_admin test identities · **forbidden in staging/production** · not an
enterprise identity · not a production audit identity · grants no deploy/sync.

## production auth (disabled)
No OIDC provider/client/JWKS · no group mapping · no production session secret
store · no production logout/revocation hardening · no production role mapping ·
MFA/conditional access live in the external IdP (not integrated).

## Production fail-closed rules
Production must reject a non-OIDC-ready config, must not use test-local auth, must
not use an ephemeral session secret, must deny unknown users, must reject unsigned
role claims, and must never auto-grant `platform_admin`.

## Step 52.2 (Stage 54B) — OIDC abstraction added, still disabled
The OIDC provider abstraction now exists as model + contracts only and stays
disabled/fail-closed (see [oidc-fail-closed-policy.md](oidc-fail-closed-policy.md)).
The validator forces `invalid` if production is enabled, if a test-local fallback
is allowed, if an unknown user would be allowed, if the default role is
privileged, or if discovery/JWKS fetch / the callback is enabled. A token's
`role`/`is_admin`/`platform_admin` claim is never authoritative
([oidc-claim-contract.md](oidc-claim-contract.md)). Production auth remains
disabled; no discovery/JWKS fetch; no real IdP.

## Step 52.3 (Stage 54C) — session hardening + role mapping
A local role mapping engine + policy now exist but stay **unconfigured**
(placeholder fixtures only); unknown users are denied, the default role is
`none`, and `platform_admin` requires an explicit mapping
([role-mapping-policy.md](role-mapping-policy.md),
[unknown-user-policy.md](unknown-user-policy.md)). Session hardening, cleanup,
forced-logout, key-rotation, break-glass, and an authorization-decision model
are added; the identity runtime-config validator fails closed on production
auth without OIDC ready, test-local fallback in production, an ephemeral
production session key, a missing production secret store, wildcard group
mapping, a non-none default role, and frontend role authority. No production
auth, no real IdP, no break-glass enabled.
