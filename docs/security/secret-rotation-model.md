# Secret Rotation Model (Step 53)

Source: [secret-rotation-model.yaml](../../infra/secrets/secret-rotation-model.yaml).

Model only — no real rotation performed; a production secret store is required
first. Rotation-without-downtime and emergency rotation (approval-required) are
modeled. Rotation plans cover: session signing key, audit HMAC keyring, OIDC
client secret, database credential, Redis credential, backup encryption key,
GitHub credential, ArgoCD repo credential, registry credential, LLM API key,
notification webhook. Every plan records the production-store dependency.

Complements the Step 52.3 session-key-rotation model
([session-key-rotation-model.md](session-key-rotation-model.md)).
