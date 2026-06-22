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
