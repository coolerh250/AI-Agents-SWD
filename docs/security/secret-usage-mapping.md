# Secret Usage Mapping (Step 53)

Source: [secret-usage-mapping.yaml](../../infra/secrets/secret-usage-mapping.yaml).

Maps each consuming component to the secret it uses, its current (non-production)
mode, and its production mode (`secret_store_ref`). Covers: session signing,
CSRF signing, OIDC client secret + client ID, database, Redis, backup encryption
key, off-host backup target, audit HMAC key, GitHub, ArgoCD repo, Kubernetes
cluster, registry, LLM API key, notification webhook, Google Drive / email-SMTP.

Every usage records blockers; the dominant blocker is
`no_production_secret_store`. No real values.
