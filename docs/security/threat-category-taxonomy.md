# Threat Category Taxonomy (Step 54.4)

Source: [`infra/security/threat-category-taxonomy.yaml`](../../infra/security/threat-category-taxonomy.yaml)

14 STRIDE-inspired + agentic-AI + supply-chain categories. Each defines a
description, affected surfaces, default severity, required mitigations, a
`productionBlocker` flag and an evidence requirement. Modeled, not enforced.

Categories: `spoofing`, `tampering`, `repudiation`, `information_disclosure`,
`denial_of_service`, `elevation_of_privilege`, `prompt_injection`, `tool_misuse`,
`agent_goal_drift`, `supply_chain_compromise`, `secret_leakage`,
`deployment_boundary_bypass`, `audit_integrity_failure`, `human_approval_bypass`.

Every threat in the [threat model baseline](threat-model-baseline.md) references one
of these category ids (asserted by `verify_threat_model_baseline.py`).

## Verify
`python scripts/verify_threat_model_baseline.py` (cross-checks categories);
`tests/test_threat_category_taxonomy.py`.
