# Security Finding Severity Taxonomy (Step 54.1)

Source of truth: [infra/security/security-finding-taxonomy.yaml](../../infra/security/security-finding-taxonomy.yaml).

Defines severities and their gate behaviour. Modeled, not enforced.

| Severity | SLA | Gate behaviour | Production blocker |
| --- | --- | --- | --- |
| critical | immediate | fail | yes (not overridable) |
| high | 7d | fail_or_explicit_approval | yes |
| medium | 30d | approval_required | no |
| low | 90d | record | no |
| informational | none | record | no |

## Special classifications (always critical, production blocker)

- `secret_leak`
- `production_credential_leak`
- `unauthenticated_deploy_path`

Verified by `scripts/verify_security_gate_policy.py` (`SECURITY_GATE_POLICY_VERIFY`) and
covered by `tests/test_security_finding_taxonomy.py`.
