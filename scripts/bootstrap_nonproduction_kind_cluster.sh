#!/usr/bin/env bash
# Step 55.1 (Stage 57B) -- bootstrap a SAFE non-production kind cluster for the
# Step 55 runtime smoke. Idempotent. Local-only; NO registry login, NO image push,
# NO public ingress / LoadBalancer, NO production secret / DB / Redis, NO ArgoCD
# sync. Builds nothing remotely: it tags already-built local compose images and
# `kind load`s them, then creates the namespace + a NON-secret in-cluster Secret
# (in-cluster service URLs only; never committed).
#
# Marker: NONPROD_CLUSTER_BOOTSTRAP: PASS | BLOCKED | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

CLUSTER=aiagents-smoke
NS=aiagents-smoke-dev
KIND_CFG=infra/kubernetes/kind/nonproduction-kind-cluster.yaml
NODE_IMAGE=kindest/node:v1.31.2
# component -> local compose image to retag as aiagents/<component>:smoke-local
COMPONENTS=(orchestrator policy-engine approval-engine audit-service)

blocked() { echo "  [BLOCKED] $1"; echo "NONPROD_CLUSTER_BOOTSTRAP: BLOCKED"; exit 0; }
fail() { echo "  [FAIL] $1"; echo "NONPROD_CLUSTER_BOOTSTRAP: FAIL"; exit 1; }

# ---- namespace guardrails (refused regardless of cluster) --------------------
case "$NS" in
  default|kube-system|argocd|production|prod|staging-prod) fail "forbidden namespace: $NS" ;;
  *prod*|*production*) fail "namespace contains a production substring: $NS" ;;
esac

# ---- tooling -----------------------------------------------------------------
command -v docker  >/dev/null 2>&1 || blocked "docker not available"
command -v kind    >/dev/null 2>&1 || blocked "kind not available"
command -v kubectl >/dev/null 2>&1 || blocked "kubectl not available"
command -v helm    >/dev/null 2>&1 || blocked "helm not available"

# ---- cluster (create if absent) ----------------------------------------------
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "  [OK] kind cluster '$CLUSTER' already present"
else
  echo "  creating kind cluster '$CLUSTER'..."
  kind create cluster --config "$KIND_CFG" --image "$NODE_IMAGE" --wait 120s || fail "kind create failed"
fi
CTX="$(kubectl config current-context 2>/dev/null || echo '')"
case "$CTX" in
  kind-aiagents-smoke) : ;;
  *prod*|*production*) fail "refusing: current context looks production" ;;
  *) kubectl config use-context "kind-${CLUSTER}" >/dev/null 2>&1 || fail "cannot select kind context" ;;
esac

# ---- images: tag local compose images + kind load (NEVER push / login) -------
for c in "${COMPONENTS[@]}"; do
  src="aiagents-test-${c}:latest"
  dst="aiagents/${c}:smoke-local"
  docker image inspect "$src" >/dev/null 2>&1 || blocked "local image missing: $src (build the compose stack first)"
  docker tag "$src" "$dst" || fail "docker tag failed for $c"
  kind load docker-image "$dst" --name "$CLUSTER" >/dev/null 2>&1 || fail "kind load failed for $c"
  echo "  [OK] loaded $dst"
done
# postgres/redis are public images; the node pulls them on demand (IfNotPresent).

# ---- namespace + NON-secret in-cluster Secret (never committed) --------------
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 \
  || fail "namespace create failed"
# Values are in-cluster service URLs with trust auth -- NO password / token / cert.
kubectl -n "$NS" create secret generic aiagents-runtime-secrets \
  --from-literal=databaseUrl="postgresql://postgres@postgres:5432/aiagents" \
  --from-literal=redisUrl="redis://redis:6379" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 \
  || fail "in-cluster secret create failed"
echo "  [OK] namespace '$NS' + in-cluster runtime secret present (not committed)"

echo "NONPROD_CLUSTER_BOOTSTRAP: PASS"
exit 0
