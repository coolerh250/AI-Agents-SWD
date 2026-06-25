#!/usr/bin/env bash
# Step 55 -- non-production Helm runtime smoke runner.
#
# Renders + (optionally) installs the ai-agents-platform chart into a NON-PRODUCTION
# namespace, ONLY when a safe non-production cluster is present. Hard guardrails:
# refuses production / default / *prod* namespaces, never creates Ingress /
# LoadBalancer / ClusterRole / CRD, never runs ArgoCD sync, never pushes an image,
# never logs into a registry, never prints a kubeconfig / token / secret,
# production_executed stays false. If kubectl/helm/kubeconfig are absent or the
# context is unsafe, it emits BLOCKED_NO_SAFE_CLUSTER (never a faked PASS).
#
# Usage: run_nonproduction_helm_smoke.sh [--dry-run-only] [--namespace NS]
#                                        [--values PATH] [--release NAME]
# Marker: NONPROD_HELM_RUNTIME_SMOKE_VERIFY: PASS | BLOCKED_NO_SAFE_CLUSTER | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

CHART="infra/kubernetes/charts/ai-agents-platform"
DRY_RUN_ONLY=0
NAMESPACE="aiagents-smoke-dev"
VALUES="$CHART/values-nonprod-smoke.yaml"
RELEASE="aiagents-smoke"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run-only) DRY_RUN_ONLY=1 ;;
    --namespace) NAMESPACE="$2"; shift ;;
    --values) VALUES="$2"; shift ;;
    --release) RELEASE="$2"; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

blocked() { echo "  [BLOCKED] $1"; echo "NONPROD_HELM_RUNTIME_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER"; exit 0; }
fail() { echo "  [FAIL] $1"; echo "NONPROD_HELM_RUNTIME_SMOKE_VERIFY: FAIL"; exit 1; }

echo "### run_nonproduction_helm_smoke: ns=$NAMESPACE release=$RELEASE dry_run_only=$DRY_RUN_ONLY"

# ---- namespace guardrails (refused regardless of cluster) --------------------
case "$NAMESPACE" in
  default|kube-system|argocd|production|prod|staging-prod) fail "forbidden namespace: $NAMESPACE" ;;
esac
case "$NAMESPACE" in
  *prod*|*production*) fail "namespace contains a production substring: $NAMESPACE" ;;
esac
case "$VALUES" in
  *prod-placeholder*|*staging-placeholder*|*values-prod*) fail "production/staging values rejected: $VALUES" ;;
esac
[ -f "$VALUES" ] || fail "values file not found: $VALUES"
echo "  [OK] namespace + values guardrails passed"

# ---- tooling presence -------------------------------------------------------
command -v kubectl >/dev/null 2>&1 || blocked "kubectl not available"
command -v helm >/dev/null 2>&1 || blocked "helm not available"
[ -n "${KUBECONFIG:-}" ] || [ -f "$HOME/.kube/config" ] || blocked "no kubeconfig present"

# ---- preflight: safe non-production context ---------------------------------
CTX="$(kubectl config current-context 2>/dev/null || echo '')"
[ -n "$CTX" ] || blocked "no current kubectl context"
case "$CTX" in
  *prod*|*production*) fail "current context looks production: <redacted>" ;;
esac
kubectl cluster-info >/dev/null 2>&1 || blocked "cluster not reachable"
[ "$(kubectl auth can-i create deployment -n "$NAMESPACE" 2>/dev/null || echo no)" = "yes" ] \
  || blocked "insufficient namespaced permission (create deployment)"

# ---- helm render (always safe) ----------------------------------------------
helm lint "$CHART" -f "$VALUES" >/dev/null 2>&1 || fail "helm lint failed"
helm template "$RELEASE" "$CHART" -f "$VALUES" -n "$NAMESPACE" >/dev/null 2>&1 \
  || fail "helm template failed"
# Refuse a chart render that would create Ingress / LoadBalancer / cluster-scoped RBAC.
RENDER="$(helm template "$RELEASE" "$CHART" -f "$VALUES" -n "$NAMESPACE" 2>/dev/null)"
if grep -qE '^kind:\s*(Ingress|ClusterRole|ClusterRoleBinding|CustomResourceDefinition)\b' <<< "$RENDER"; then
  fail "render contains forbidden cluster-scoped/ingress resource"
fi
if grep -qE 'type:\s*LoadBalancer' <<< "$RENDER"; then
  fail "render contains a LoadBalancer service"
fi
echo "  [OK] helm lint + template render passed; no Ingress/LoadBalancer/cluster-scoped resource"

if [ "$DRY_RUN_ONLY" = "1" ]; then
  echo "  [OK] --dry-run-only: render verified, no install performed"
  echo "NONPROD_HELM_RUNTIME_SMOKE_VERIFY: PASS"
  exit 0
fi

# ---- install into the non-production namespace only --------------------------
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE" || fail "namespace create failed"
helm upgrade --install "$RELEASE" "$CHART" -f "$VALUES" -n "$NAMESPACE" --wait --timeout 5m \
  || fail "helm install/upgrade failed"
echo "  [OK] helm install/upgrade into $NAMESPACE complete"
echo "NONPROD_HELM_RUNTIME_SMOKE_VERIFY: PASS"
exit 0
