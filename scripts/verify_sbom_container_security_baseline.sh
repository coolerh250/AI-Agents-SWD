#!/usr/bin/env bash
# Step 54.3 -- combined SBOM / image digest / container security baseline.
#
# Chains the Step 51 + 52 + 53 + 54.1 + 54.2 baselines, then the SBOM capability /
# boundary / local-SBOM / image-inventory / digest-policy / Dockerfile-security /
# runtime-alignment / image-policy / signing-attestation / operations / Admin
# Console / safety verifiers and the targeted tests. LOCAL-ONLY: NO registry login,
# NO image pull/push, NO signing, NO attestation, NO external upload, NO production
# gate, NO full regression.
#
# Marker: SBOM_CONTAINER_SECURITY_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51 Kubernetes/Helm/ArgoCD integrated baseline"
bash scripts/verify_kubernetes_helm_argocd_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "2. Step 52 identity foundation integrated baseline"
bash scripts/verify_identity_foundation_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "3. Step 53 secret management foundation baseline"
bash scripts/verify_secret_management_foundation_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "4. Step 54.1 security & supply chain policy baseline"
bash scripts/verify_security_supply_chain_policy_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "5. Step 54.2 local scan toolchain baseline"
bash scripts/verify_security_scan_toolchain_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "6. SBOM capability inventory verify"
"$PY" scripts/verify_sbom_capability_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "7. SBOM generation boundary verify"
"$PY" scripts/verify_sbom_generation_boundary.py | tail -3; need ${PIPESTATUS[0]}

step "8. local SBOM baseline verify"
"$PY" scripts/verify_local_sbom_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "9. container image inventory verify"
"$PY" scripts/verify_container_image_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "10. image digest policy verify"
"$PY" scripts/verify_image_digest_policy.py | tail -3; need ${PIPESTATUS[0]}

step "11. Dockerfile security inventory verify"
"$PY" scripts/verify_dockerfile_security_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "12. container runtime security alignment verify"
"$PY" scripts/verify_container_runtime_security_alignment.py | tail -3; need ${PIPESTATUS[0]}

step "13. local image policy baseline verify"
"$PY" scripts/verify_local_image_policy_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "14. image signing / attestation model verify"
"$PY" scripts/verify_image_signing_attestation_model.py | tail -3; need ${PIPESTATUS[0]}

step "15. container security operations visibility verify"
"$PY" scripts/verify_container_security_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "16. Admin Console container security verify"
"$PY" scripts/verify_admin_console_container_security.py | tail -3; need ${PIPESTATUS[0]}

step "17. container security safety fields verify"
"$PY" scripts/verify_container_security_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "18. targeted sbom / container security tests"
"$PY" -m pytest -q \
  tests/test_sbom_capability_inventory.py \
  tests/test_sbom_generation_boundary.py \
  tests/test_sbom_artifact_schema.py \
  tests/test_local_sbom_baseline.py \
  tests/test_container_image_inventory.py \
  tests/test_image_digest_policy.py \
  tests/test_image_tag_policy.py \
  tests/test_dockerfile_security_inventory.py \
  tests/test_container_runtime_security_alignment.py \
  tests/test_image_vulnerability_scan_capability.py \
  tests/test_image_vulnerability_result_schema.py \
  tests/test_local_image_policy_baseline.py \
  tests/test_image_signing_attestation_model.py \
  tests/test_registry_credential_boundary.py \
  tests/test_container_security_evidence_model.py \
  tests/test_container_security_operations_api.py \
  tests/test_container_security_operations_read_only.py \
  tests/test_container_security_safety_fields.py \
  tests/test_admin_console_container_security.py \
  tests/test_container_security_no_mutation_actions.py \
  tests/test_container_security_production_not_ready.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "19. safety posture: container security + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('security_registry_login_enabled'), d.get('security_image_push_enabled'), d.get('security_image_signing_configured'), d.get('security_container_production_ready'), d.get('security_sbom_baseline_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x x")
case "$pa" in
  "False False False False True 0")
    echo "  [PASS] no registry login/image push/signing; container not production ready; sbom baseline enabled; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "SBOM_CONTAINER_SECURITY_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "SBOM_CONTAINER_SECURITY_BASELINE_VERIFY: PASS"
