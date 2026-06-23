# Security & Supply Chain Verification (Step 54.1)

All verifiers are read-only. They run **no scanner**, make **no external call**, perform
**no GitHub write / image push / registry login**, and execute **no production action**.

## Verifiers and markers

| Verifier | Marker | Live server? |
| --- | --- | --- |
| `scripts/verify_security_asset_inventory.py` | `SECURITY_ASSET_INVENTORY_VERIFY` | no |
| `scripts/verify_supply_chain_inventory.py` | `SUPPLY_CHAIN_INVENTORY_VERIFY` | no |
| `scripts/verify_security_scan_policy_baseline.py` | `SECURITY_SCAN_POLICY_BASELINE_VERIFY` | no |
| `scripts/verify_security_evidence_model.py` | `SECURITY_EVIDENCE_MODEL_VERIFY` | no |
| `scripts/verify_security_gate_policy.py` | `SECURITY_GATE_POLICY_VERIFY` | no |
| `scripts/verify_security_operations_visibility.py` | `SECURITY_OPERATIONS_VISIBILITY_VERIFY` | yes |
| `scripts/verify_admin_console_security_posture.py` | `ADMIN_CONSOLE_SECURITY_POSTURE_VERIFY` | optional |
| `scripts/verify_security_safety_fields.py` | `SECURITY_SAFETY_FIELDS_VERIFY` | yes |
| `scripts/verify_security_supply_chain_policy_baseline.sh` | `SECURITY_SUPPLY_CHAIN_POLICY_BASELINE_VERIFY` | yes |

The combined baseline chains the Step 51 + Step 52 + Step 53 baselines first, then the eight
security verifiers, the targeted tests, and the `/operations/safety` posture check.

## Running

```bash
# file-based verifiers (no server)
python scripts/verify_security_asset_inventory.py
python scripts/verify_supply_chain_inventory.py
python scripts/verify_security_scan_policy_baseline.py
python scripts/verify_security_evidence_model.py
python scripts/verify_security_gate_policy.py

# live verifiers require the orchestrator (rebuilt to pick up new code + catalogs)
python scripts/verify_security_operations_visibility.py
python scripts/verify_admin_console_security_posture.py
python scripts/verify_security_safety_fields.py

# combined baseline (chains Step 51/52/53 + the above + targeted tests)
./scripts/verify_security_supply_chain_policy_baseline.sh
```

On the test server (10.0.1.31), verifiers importing the SDK must run under
`.venv/bin/python`, and the live verifiers require an orchestrator rebuild
(`docker compose build orchestrator && docker compose up -d orchestrator`) so the new
`/operations/security/*` routes and the committed `infra/security/` catalogs are present.

## Expected safety posture

`GET /operations/safety` returns:

```
security_foundation_enabled=true
security_foundation_status=modeled_not_enforced
security_sast_configured=false
security_dependency_scan_configured=false
security_secret_scan_configured=false
security_sbom_configured=false
security_image_digest_policy_defined=true
security_image_vulnerability_policy_defined=true
security_threat_model_required=true
security_release_risk_summary_required=true
security_evidence_model_defined=true
security_finding_taxonomy_defined=true
security_gate_fail_closed_policy_defined=true
security_production_ready=false
supply_chain_inventory_present=true
supply_chain_github_write_enabled=false
supply_chain_pr_creation_enabled=false
supply_chain_image_push_enabled=false
supply_chain_registry_login_enabled=false
supply_chain_external_scanner_upload_enabled=false
production_executed_true_count=0
```
