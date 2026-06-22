# Disabled Production OIDC Config (Step 52.2)

`infra/identity/production-oidc-disabled-config.yaml` is a placeholder for a
future production OIDC configuration. It exists to prove production auth is
**fail-closed today**, and must never be treated as enabled or ready by the
runtime.

```yaml
auth:
  mode: oidc
  enabled: false
  productionEnabled: false
  failClosed: true
  testLocalFallbackAllowed: false
status:
  configured: false
  ready: false
  reason: required_fields_missing
```

## Fields required before enablement

`issuer_url`, `discovery_metadata`, `jwks_uri`, `client_id_secret_ref`,
`client_secret_secret_ref`, `redirect_uri`, `claim_contract`, `role_mapping`,
`production_session_secret_store`, `audit_subject_mapping`, `logout_strategy`,
`operator_approval`. None is configured.

## Loader behaviour

`load_oidc_config()` reads only committed YAML (never a real secret from
`.env`), performs no network call, and returns one of:

* `disabled_unconfigured` — current state (no required field configured).
* `disabled_missing_required_fields` — some but not all configured.
* `ready_for_future_enablement` — all configured, production still gated.
* `invalid` — any fail-closed rule tripped.

The validator forces `invalid` when production is enabled, when a test-local
fallback is allowed, when an enabled config is missing required fields, when an
unknown user would be allowed, when the default role is privileged, when
discovery/JWKS fetch or the callback is enabled, or when a secret-shaped literal
is present. See [oidc-fail-closed-policy.md](oidc-fail-closed-policy.md).

Step 52.3 adds a complementary identity runtime-config validator
(`shared/sdk/identity/identity_runtime_config.py`) that fails closed on OIDC
enabled without a configured role mapping, wildcard group mapping, frontend role
authority, an ephemeral production session key, a missing production secret
store, and session key rotation missing in production — see
[role-mapping-policy.md](role-mapping-policy.md).

Verifier marker: `OIDC_FAIL_CLOSED_CONFIG_VERIFY: PASS`.
