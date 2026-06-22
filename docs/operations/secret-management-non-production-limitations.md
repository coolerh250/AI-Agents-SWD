# Secret Management Non-Production Limitations (Step 53)

The secret management foundation is **modeled, fail-closed, and not configured**.
Required before any production secret use:

* No production secret store connected (no Vault / GCP SM / AWS SM / Azure KV).
* No real OIDC client secret, session signing key store, or backup encryption
  key store.
* No real database / Redis credential store; dev/test use trust-auth / no-auth
  (non-production).
* No real GitHub / ArgoCD / Kubernetes / registry credential.
* No secret rotation backend.
* No Kubernetes Secret created; no ExternalSecret / SealedSecret enabled.
* Break-glass credential disabled (depends on the production approval model).

## Never allowed

Real secret committed (client secret, JWT, token, private key, kubeconfig,
GitHub/ArgoCD token, registry credential, DB URL with password, webhook secret);
a secret read/write/rotate endpoint; an Admin Console reveal/copy/upload/rotate/
configure action; a production secret store enabled; production auth/action.

Claude Code reports observations only and does not decide production readiness.
