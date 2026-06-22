# Secret Redaction Policy (Step 53)

Source: [secret-redaction-policy.yaml](../../infra/secrets/secret-redaction-policy.yaml);
helper: [secret_redaction.py](../../shared/sdk/secrets_foundation/secret_redaction.py).

Redacts values whose key contains: secret, token, password, key, private,
credential, bearer, cookie, csrf, jwt. Redacts value shapes: JWT, private key
block, high-entropy string, OAuth code, DB URL with password, webhook URL,
kubeconfig, service-account token, registry auth.

Applied to: operations API, Admin Console, audit metadata, verification output,
runtime reports. Redaction token: `***REDACTED***`. The read-only secret
operations API + report builder route responses through `redact()`.
