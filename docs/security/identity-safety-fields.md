# Identity Safety Fields (Step 52.4)

`/operations/safety` carries flat, read-only identity fields (booleans / enums /
counts only) sourced from the committed identity posture summary. Absent summary
→ safe `unknown` posture; `identity_production_ready` is **always** false.

## Expected values

| Field | Value |
|---|---|
| `identity_posture_status` | `modeled_fail_closed_not_enabled` |
| `identity_production_ready` | false |
| `identity_production_auth_enabled` | false |
| `identity_test_local_enabled` | true |
| `identity_test_local_production_allowed` | false |
| `identity_oidc_abstraction_enabled` | true |
| `identity_oidc_enabled` / `identity_oidc_production_enabled` | false |
| `identity_oidc_discovery_fetched` / `identity_oidc_jwks_fetched` | false |
| `identity_oidc_callback_enabled` / `identity_oidc_token_exchange_enabled` | false |
| `identity_oidc_real_provider_configured` / `identity_oidc_secret_committed` | false |
| `identity_session_hardened` | true |
| `identity_session_raw_token_persisted` | false |
| `identity_session_cleanup_available` | true |
| `identity_session_concurrency_enforced` | false |
| `identity_session_forced_logout_supported` | true |
| `identity_session_key_rotation_ready` | false |
| `identity_session_production_secret_store_configured` | false |
| `identity_role_mapping_engine_present` | true |
| `identity_role_mapping_configured` | false |
| `identity_unknown_user_behavior` | deny |
| `identity_default_role` | none |
| `identity_platform_admin_auto_grant` | false |
| `identity_frontend_role_authority` | false |
| `identity_break_glass_enabled` / `identity_break_glass_route_present` | false |
| `identity_break_glass_requires_future_approval` | true |
| `identity_human_acceptance_is_deployment` | false |
| `identity_verification_rerun_allowlisted_only` | true |
| `identity_platform_admin_infrastructure_authority` | false |
| `production_executed_true_count` | 0 |

Verifier: `IDENTITY_SAFETY_FIELDS_VERIFY`.
