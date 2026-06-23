# Security Scan Toolchain Verification (Step 54.2)

All verifiers are local. They run no external scanner, make no network call, perform no GitHub
write / image push / registry login, and execute no production action.

## Verifiers and markers

| Verifier | Marker | Live server? |
| --- | --- | --- |
| `verify_local_scanner_capabilities.py` | `LOCAL_SCANNER_CAPABILITIES_VERIFY` | no |
| `verify_scanner_execution_boundary.py` | `SCANNER_EXECUTION_BOUNDARY_VERIFY` | no |
| `verify_scan_target_catalog.py` | `SCAN_TARGET_CATALOG_VERIFY` | no |
| `verify_local_secret_scan_baseline.py` | `LOCAL_SECRET_SCAN_BASELINE_VERIFY` | no (runs runner) |
| `verify_local_sast_baseline.py` | `LOCAL_SAST_BASELINE_VERIFY` | no (runs runner) |
| `verify_local_dependency_scan_baseline.py` | `LOCAL_DEPENDENCY_SCAN_BASELINE_VERIFY` | no (runs runner) |
| `verify_security_scan_result_normalization.py` | `SECURITY_SCAN_RESULT_NORMALIZATION_VERIFY` | no |
| `verify_security_scan_operations_visibility.py` | `SECURITY_SCAN_OPERATIONS_VISIBILITY_VERIFY` | yes |
| `verify_admin_console_scan_posture.py` | `ADMIN_CONSOLE_SCAN_POSTURE_VERIFY` | optional |
| `verify_security_scan_safety_fields.py` | `SECURITY_SCAN_SAFETY_FIELDS_VERIFY` | yes |
| `verify_security_scan_toolchain_baseline.sh` | `SECURITY_SCAN_TOOLCHAIN_BASELINE_VERIFY` | yes |

The combined baseline chains the Step 51 + 52 + 53 + 54.1 baselines first, then the ten Step
54.2 verifiers, the targeted tests, and the `/operations/safety` posture check.

## Running

```bash
# run the local scanners (writes redacted reports to .runtime/security/, never committed)
python scripts/run_local_secret_scan.py
python scripts/run_local_sast_scan.py
python scripts/run_local_dependency_scan.py
python scripts/normalize_security_scan_results.py

# combined baseline (chains prior baselines + the above + targeted tests)
./scripts/verify_security_scan_toolchain_baseline.sh
```

On the test server (10.0.1.31), run under `.venv/bin/python` (`PYTHON=.venv/bin/python`); the
live verifiers require the orchestrator rebuilt to pick up the new `/operations/security/scans/*`
routes. Runtime scan reports are not present in the orchestrator image, so live scan views
degrade to `not_run`.

## Expected safety posture

`security_local_scan_baseline_enabled=true`, `security_local_secret_scan_configured=true`,
`security_local_sast_configured=limited_custom_baseline`,
`security_local_dependency_scan_configured=limited_manifest_baseline`,
`security_scan_external_upload_enabled=false`, `security_scan_network_enabled=false`,
`security_scan_token_required=false`, `security_scan_run_endpoint_enabled=false`,
`security_scan_result_normalization_enabled=true`, `security_scan_reports_committed=false`,
`security_scan_production_gate_enabled=false`, `security_scan_production_ready=false`,
`security_*_last_status` ∈ {not_run, completed_*, tool_unavailable},
`production_executed_true_count=0`.
