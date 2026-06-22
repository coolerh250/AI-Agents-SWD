# Disabled Production Secret Store Config (Step 53)

Source: [production-secret-store-disabled-config.yaml](../../infra/secrets/production-secret-store-disabled-config.yaml).

Placeholder proving production secret management is fail-closed today:

```yaml
productionSecretStore:
  enabled: false
  configured: false
  provider: disabled
  failClosed: true
  readSecretValuesEnabled: false
  writeSecretValuesEnabled: false
  rotationEnabled: false
  productionReady: false
```

No real provider, endpoint, credential, project ID, vault path, or tenant.
Required before: production OIDC, production session key rotation, production
backup, production GitOps repo credentials, production deployment. The SDK
`DisabledSecretStoreProvider.read_secret_value` raises
`SecretValueAccessDisabledError` — no value read is possible this stage.
