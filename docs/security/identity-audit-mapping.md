# Identity-to-Audit Mapping (Step 52.1 / Stage 54A)

Source: [identity-audit-mapping.yaml](../../infra/identity/identity-audit-mapping.yaml);
`shared/sdk/operator_actions/audit_events.py`.

**Recorded:** actor `identity_key`, `role`, `action_type`/`action_key`, target,
`policy_status`, `status`, `verification_key`, `result_marker`,
`production_executed=false`, `controlled_only=true`.

**Never recorded:** raw session token, CSRF token, raw confirmation nonce, session
signing secret, chain-of-thought, free-text reason dump. Confirmation nonce is
sha256-hashed; the idempotency key is a charset-bounded non-secret correlation
key (not an auth token).

Human acceptance and verification rerun are both traceable to an identity. A
future OIDC subject field is planned (52.2/52.3) but **not** implemented here.

## Step 52.3 (Stage 54C) — planned identity audit enrichment

`futureOidcEnrichment` (enabled=false) reserves audit fields for a future
production OIDC + role-mapping flow: `provider_key`, `subject_hash`,
`email_hash`, `group_mapping_rule_id`, `role_mapping_decision`,
`unknown_user_denied`, `session_key_id`, `session_revoked`,
`forced_logout_reason`. Redaction rules forbid persisting a raw email list, raw
group object IDs (use the mapping rule id), raw tokens, raw OIDC claims, CSRF,
nonce, or chain-of-thought. Subject and email are recorded only as
`sha256` hashes. Planned only — nothing is emitted in this step.
