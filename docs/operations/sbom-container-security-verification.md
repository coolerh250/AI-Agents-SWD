# SBOM / Container Security Verification (Step 54.3)

All verifiers are local. They run no registry login, no image pull/push, no image signing, no
attestation, no external upload, and no production action.

## Verifiers and markers

| Verifier | Marker | Live server? |
| --- | --- | --- |
| `verify_sbom_capability_inventory.py` | `SBOM_CAPABILITY_INVENTORY_VERIFY` | no |
| `verify_sbom_generation_boundary.py` | `SBOM_GENERATION_BOUNDARY_VERIFY` | no |
| `verify_local_sbom_baseline.py` | `LOCAL_SBOM_BASELINE_VERIFY` | no (runs runner) |
| `verify_container_image_inventory.py` | `CONTAINER_IMAGE_INVENTORY_VERIFY` | no |
| `verify_image_digest_policy.py` | `IMAGE_DIGEST_POLICY_VERIFY` | no |
| `verify_dockerfile_security_inventory.py` | `DOCKERFILE_SECURITY_INVENTORY_VERIFY` | no |
| `verify_container_runtime_security_alignment.py` | `CONTAINER_RUNTIME_SECURITY_ALIGNMENT_VERIFY` | no |
| `verify_local_image_policy_baseline.py` | `LOCAL_IMAGE_POLICY_BASELINE_VERIFY` | no (runs runner) |
| `verify_image_signing_attestation_model.py` | `IMAGE_SIGNING_ATTESTATION_MODEL_VERIFY` | no |
| `verify_container_security_operations_visibility.py` | `CONTAINER_SECURITY_OPERATIONS_VISIBILITY_VERIFY` | yes |
| `verify_admin_console_container_security.py` | `ADMIN_CONSOLE_CONTAINER_SECURITY_VERIFY` | no |
| `verify_container_security_safety_fields.py` | `CONTAINER_SECURITY_SAFETY_FIELDS_VERIFY` | yes |
| `verify_sbom_container_security_baseline.sh` | `SBOM_CONTAINER_SECURITY_BASELINE_VERIFY` | yes |

The combined baseline chains the Step 51 + 52 + 53 + 54.1 + 54.2 baselines first, then the
twelve Step 54.3 verifiers, the targeted tests, and the `/operations/safety` posture check.

## Running

```bash
# run the local SBOM + image policy baselines (redacted reports to .runtime/security/, never committed)
python scripts/run_local_sbom_baseline.py
python scripts/run_local_image_policy_scan.py

# combined baseline (chains prior baselines + the above + targeted tests)
./scripts/verify_sbom_container_security_baseline.sh
```

On the test server (10.0.1.31), run under `.venv/bin/python` (`PYTHON=.venv/bin/python`); the
live verifiers require the orchestrator rebuilt to pick up the new
`/operations/security/{sbom,images}/*` routes. Runtime SBOM / image-policy reports are not in the
orchestrator image, so live SBOM / image-policy views degrade to `not_run`.

## Expected safety posture

`security_sbom_baseline_enabled=true`, `security_sbom_generation_local_only=true`,
`security_sbom_external_upload_enabled=false`, `security_sbom_runtime_reports_committed=false`,
`security_container_image_inventory_present=true`, `security_image_digest_policy_defined=true`,
`security_image_digest_pinning_complete=false`, `security_latest_tag_detected=false`,
`security_dockerfile_security_inventory_present=true`, `security_dockerfile_non_root_complete=false`,
`security_container_runtime_alignment_present=true`,
`security_image_vulnerability_scan_configured=limited_policy_baseline`,
`security_image_vulnerability_cve_scan_performed=false`, `security_image_policy_scan_enabled=true`,
`security_image_policy_findings_present=true`, `security_image_signing_configured=false`,
`security_image_attestation_configured=false`, `security_registry_login_enabled=false`,
`security_image_push_enabled=false`, `security_container_production_ready=false`,
`production_executed_true_count=0`.
