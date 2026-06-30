# Production Credential Readiness Model (Step 63A)

Source: [`infra/readiness/production-credential-readiness-model.yaml`](../../infra/readiness/production-credential-readiness-model.yaml).

Records only whether a production secret **reference** is configured — never the credential
value, never a sensitive secret name. Each reference carries only `{name, configured}`. No
production credential is created or read; no secret is committed
(`reads_credential_values: false`, `creates_credentials: false`, `exposes_secret: false`).
Every reference is currently `not_configured` → contributes to `no_go`.
