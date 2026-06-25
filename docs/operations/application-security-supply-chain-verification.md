# Application Security & Supply Chain — Verification (Step 54.4 / Step 54)

## Combined baseline
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  ./scripts/verify_application_security_supply_chain_baseline.sh
```
Marker: `APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY: PASS`.

It chains (deduped, each once via `scripts/lib/baseline_run_guard.sh`):
Step 51 → 52 → 53 → 54.1 → 54.2 → 54.3, then the Step 54.4 verifiers.

## Individual verifiers + markers
| Verifier | Marker |
|---|---|
| `verify_threat_model_baseline.py` | `THREAT_MODEL_BASELINE_VERIFY` |
| `verify_agent_threat_model.py` | `AGENT_THREAT_MODEL_VERIFY` |
| `verify_supply_chain_threat_model.py` | `SUPPLY_CHAIN_THREAT_MODEL_VERIFY` |
| `verify_runtime_gitops_threat_model.py` | `RUNTIME_GITOPS_THREAT_MODEL_VERIFY` |
| `verify_release_risk_summary_model.py` | `RELEASE_RISK_SUMMARY_MODEL_VERIFY` |
| `verify_security_evidence_package.py` | `SECURITY_EVIDENCE_PACKAGE_VERIFY` |
| `verify_release_risk_summary.py` | `RELEASE_RISK_SUMMARY_VERIFY` |
| `verify_security_readiness_report.py` | `SECURITY_READINESS_REPORT_VERIFY` |
| `verify_security_integrated_operations_visibility.py` (live) | `SECURITY_INTEGRATED_OPERATIONS_VISIBILITY_VERIFY` |
| `verify_admin_console_security_integrated.py` | `ADMIN_CONSOLE_SECURITY_INTEGRATED_VERIFY` |
| `verify_security_integrated_safety_fields.py` (live) | `SECURITY_INTEGRATED_SAFETY_FIELDS_VERIFY` |

Live verifiers require the running orchestrator (`ORCHESTRATOR_URL`). Read-only
endpoints under `GET /operations/security/{threat-model,release-risk,evidence,
readiness,step54}/*`. Full regression: `./scripts/run_full_regression.sh --full
--json-report` → `FULL_REGRESSION_VERIFY: PASS` or
`PASS_WITH_NON_PRODUCTION_LIMITATIONS`.
