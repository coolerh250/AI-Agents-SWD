# Secret Audit Model (Step 53)

Source: [secret-audit-model.yaml](../../infra/secrets/secret-audit-model.yaml).

Future audit events (model only): `secret_ref_registered`, `secret_ref_updated`,
`secret_rotation_requested`, `secret_rotation_completed`, `secret_access_denied`,
`secret_store_unavailable`, `secret_validation_failed`.

Records actor role, reason, approval reference, correlation id. **Never** records
a secret value, raw token, sensitive secret path, private key, client secret,
password, or JWT. Production mutation deferred.
