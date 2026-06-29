# Release Governance — Verification (Step 60)

Combined: `scripts/verify_release_deployment_governance_baseline.sh`
→ `RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY: PASS | BLOCKED | FAIL`

It chains the Step 59 combined (which dedupes Step 52–58 + the tenant strategy note + the
9 sandbox-GitHub verifiers), then runs the 11 Step 60 verifiers, the targeted tests, and
the safety posture check.

| Verifier | Marker |
| --- | --- |
| Policy | `RELEASE_GOVERNANCE_POLICY_VERIFY` |
| Release candidate model | `RELEASE_CANDIDATE_MODEL_VERIFY` |
| Deployment intent model | `DEPLOYMENT_INTENT_MODEL_VERIFY` |
| Promotion boundary | `PROMOTION_BOUNDARY_MODEL_VERIFY` |
| Evidence package | `RELEASE_EVIDENCE_PACKAGE_VERIFY` |
| Readiness decision | `RELEASE_READINESS_DECISION_VERIFY` |
| Rollback requirement | `ROLLBACK_REQUIREMENT_MODEL_VERIFY` |
| Runtime (live) | `RELEASE_GOVERNANCE_RUNTIME_VERIFY` |
| Operations visibility (live) | `RELEASE_GOVERNANCE_OPERATIONS_VISIBILITY_VERIFY` |
| Admin Console | `ADMIN_CONSOLE_RELEASE_GOVERNANCE_VERIFY` |
| Safety fields (live) | `RELEASE_GOVERNANCE_SAFETY_FIELDS_VERIFY` |

## Targeted tests (0 skipped)
`tests/test_release_governance_{policy,candidate_model,deployment_intent_model,
promotion_boundary_model,evidence_package,readiness_decision,rollback_requirement_model,
runtime,operations_api,safety_fields,no_production_actions}.py` and
`tests/test_admin_console_release_governance.py`.

## A verifier FAILs if
production deploy allowed · production target accepted · ArgoCD production sync allowed ·
GitHub merge allowed · image push / registry login allowed · GitHub release/tag creation
or workflow dispatch enabled · release candidate `production_ready=true` · a deployment
intent executes a deploy · Admin Console exposes a deploy/sync/merge/image-push/release
control · secret/token/kubeconfig exposed · `production_executed_true_count != 0`.

## Run
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  bash scripts/verify_release_deployment_governance_baseline.sh
```
