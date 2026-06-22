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
