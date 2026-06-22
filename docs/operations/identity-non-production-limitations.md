# Identity Non-Production Limitations (Step 52.4)

The Step 52 identity foundation is **modeled, fail-closed, and not enabled**.
The following are intentionally absent and are required before any production
identity rollout:

* No real OIDC provider configured (issuer / client ID / client secret / redirect
  URIs all unconfigured).
* No OIDC discovery fetch, no JWKS fetch.
* No OIDC callback, no authorization-code / token exchange, no real token
  validation.
* No production auth; test-local signed sessions are non-production only and may
  never fall back in production.
* No production session secret store; the session signing key is a runtime key
  file / ephemeral secret (not production-ready). — **Step 53**.
* No real group→role mapping (engine present, placeholder fixtures only).
* No production session key rotation backend.
* Break-glass disabled (depends on the production approval model). — **Step 60**.
* No production approval identity chain. — **Step 60**.

## Allowed as non-production limitations in full regression

Production OIDC disabled, no real IdP, no discovery, no JWKS, no production
secret store, no real group mapping, no production session key rotation, no
break-glass, no production approval identity chain, no Kubernetes cluster
connected, no ArgoCD sync, no production deployment.

## Never allowed

Production auth enabled, OIDC/token/secret leak, raw session token persisted,
unknown user allowed, platform_admin auto-granted, runtime write endpoint, Admin
Console identity mutation, audit failure, tamper residue, production execution,
secret committed, GitHub write, PR creation, deployment action.

Claude Code reports observations only and does not decide production identity
readiness.
