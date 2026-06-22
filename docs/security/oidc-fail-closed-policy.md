# OIDC Fail-Closed Policy (Step 52.2)

The OIDC abstraction is disabled by default and the validator fails closed.
`infra/identity/oidc-safety-policy-catalog.yaml` enumerates the invariants;
`shared/sdk/identity/oidc_config.py::validate_oidc_inputs` enforces them.

## Invariants (catalog)

| Key | Severity |
|---|---|
| `oidc_must_be_disabled_until_configured` | critical |
| `no_oidc_secret_in_repo` | critical |
| `no_oidc_discovery_network_call_in_step_52_2` | critical |
| `no_jwks_fetch_in_step_52_2` | critical |
| `no_test_local_fallback_in_production` | critical |
| `unknown_user_must_deny` | critical |
| `frontend_role_claim_not_authoritative` | critical |
| `platform_admin_requires_explicit_mapping` | high |
| `callback_disabled_until_token_validation_ready` | critical |

## Validator -> `invalid`

The validator forces status `invalid` when any of these holds:

* production OIDC enabled;
* test-local fallback allowed for production auth;
* config `enabled` while required fields are missing;
* `unknown_user_behavior` is not `deny`;
* default role is `operator` or `platform_admin`;
* discovery fetch, JWKS fetch, or the callback is enabled;
* a secret-shaped literal is present in the config text.

Otherwise the status is `disabled_unconfigured` (current),
`disabled_missing_required_fields`, or `ready_for_future_enablement`.

## Verification

* `OIDC_PROVIDER_ABSTRACTION_VERIFY`
* `OIDC_FAIL_CLOSED_CONFIG_VERIFY`
* `OIDC_NO_SECRET_LEAK_VERIFY`
* `OIDC_DISABLED_PRODUCTION_BASELINE_VERIFY` (combined; also re-runs the Step
  52.1 / Step 50 / Step 51 baselines and confirms `production_executed_true_count=0`).
