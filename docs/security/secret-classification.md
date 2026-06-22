# Secret Classification (Step 53)

Source: [secret-classification.yaml](../../infra/secrets/secret-classification.yaml).

| Class | Handling | Examples |
|---|---|---|
| critical | secret store only | OIDC client secret, session signing key, backup encryption key, audit HMAC keyring |
| high | secret store only | DB/Redis credential, GitHub/ArgoCD/registry credential, CSRF/cookie key |
| medium | secret store only | notification webhook, storage credential |
| public-config | config allowed (not secret) | OIDC issuer URL, JWKS URI, redirect URI, client ID |
| placeholder | allowed if clearly disabled | disabled store reference |

OIDC issuer URL is public config (no real value this stage); client ID is a
non-secret reference (no real value this stage); client secret, session signing
key, backup encryption key, and audit HMAC key must be secret references.
