#!/usr/bin/env bash
# Step 56 (Stage 58A) -- non-production ArgoCD manual-sync runner.
#
# Real, guard-railed manual sync on the LOCAL kind cluster only. Idempotent. Refuses
# production context / namespace / default / kube-system, refuses auto-sync / prune /
# self-heal, never creates Ingress / LoadBalancer, never exposes the ArgoCD server,
# never prints a token / admin password / kubeconfig, never commits the runtime
# report. production_executed stays false.
#
# Marker: NONPROD_ARGOCD_MANUAL_SYNC_RUN: PASS | BLOCKED | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
ARGOCD_NS=argocd-nonprod
DEST_NS=aiagents-smoke-dev
PROJECT=aiagents-nonprod
APP=aiagents-smoke
ARGOCD_VERSION=v2.13.3
PROJ_MANIFEST=infra/gitops/nonproduction/aiagents-nonprod-project.yaml
APP_MANIFEST=infra/gitops/nonproduction/aiagents-smoke-application.yaml

blocked() { echo "  [BLOCKED] $1"; echo "NONPROD_ARGOCD_MANUAL_SYNC_RUN: BLOCKED"; exit 0; }
fail() { echo "  [FAIL] $1"; echo "NONPROD_ARGOCD_MANUAL_SYNC_RUN: FAIL"; exit 1; }

# ---- namespace guardrails (refused regardless of cluster) --------------------
for ns in "$ARGOCD_NS" "$DEST_NS"; do
  case "$ns" in
    default|kube-system|argocd|production|prod|staging-prod) fail "forbidden namespace: $ns" ;;
    *production*) fail "namespace contains a production substring: $ns" ;;
  esac
done

# ---- tooling + safe context --------------------------------------------------
command -v kubectl >/dev/null 2>&1 || blocked "kubectl not available"
command -v helm >/dev/null 2>&1 || blocked "helm not available"
CTX="$(kubectl config current-context 2>/dev/null || echo '')"
case "$CTX" in
  kind-aiagents-smoke) : ;;
  *prod*|*production*) fail "refusing: current context looks production" ;;
  "") blocked "no current kubectl context" ;;
  *) fail "refusing: unexpected context (not the kind non-production cluster)" ;;
esac

# ---- Step 55 runtime smoke must still PASS -----------------------------------
echo "### verifying Step 55 runtime smoke still PASS"
"$PY" scripts/run_nonproduction_runtime_smoke.py >/tmp/_s55.$$ 2>&1 || true
if ! grep -q "NONPROD_RUNTIME_SMOKE_RUN: PASS" /tmp/_s55.$$; then
  rm -f /tmp/_s55.$$; fail "Step 55 runtime smoke is not PASS; aborting"
fi
rm -f /tmp/_s55.$$
echo "  [OK] Step 55 runtime smoke PASS"

# ---- ensure non-production ArgoCD (install if absent) ------------------------
if kubectl -n "$ARGOCD_NS" get statefulset argocd-application-controller >/dev/null 2>&1; then
  echo "  [OK] ArgoCD already present in $ARGOCD_NS"
else
  echo "### installing non-production ArgoCD ${ARGOCD_VERSION} into $ARGOCD_NS"
  kubectl create namespace "$ARGOCD_NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1
  local_dir="$(mktemp -d)"
  curl -sSL -o "$local_dir/install.yaml" \
    "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" \
    || fail "could not download ArgoCD install manifest"
  printf 'namespace: %s\nresources:\n  - install.yaml\n' "$ARGOCD_NS" > "$local_dir/kustomization.yaml"
  kubectl apply -k "$local_dir" >/dev/null 2>&1 || fail "ArgoCD install failed"
  rm -rf "$local_dir"
  # kustomize does not rewrite ClusterRoleBinding subject namespaces -> patch them.
  for crb in argocd-application-controller argocd-server; do
    kubectl patch clusterrolebinding "$crb" --type=json \
      -p "[{\"op\":\"replace\",\"path\":\"/subjects/0/namespace\",\"value\":\"${ARGOCD_NS}\"}]" >/dev/null 2>&1 || true
  done
  # No SSO / applicationset / notifications in this non-production install.
  kubectl -n "$ARGOCD_NS" scale deploy argocd-dex-server argocd-applicationset-controller \
    argocd-notifications-controller --replicas=0 >/dev/null 2>&1 || true
  kubectl -n "$ARGOCD_NS" rollout status deploy/argocd-repo-server --timeout=150s >/dev/null 2>&1 || fail "repo-server not ready"
  kubectl -n "$ARGOCD_NS" rollout status statefulset/argocd-application-controller --timeout=150s >/dev/null 2>&1 || fail "controller not ready"
fi

# ---- no external exposure ----------------------------------------------------
[ "$(kubectl -n "$ARGOCD_NS" get svc argocd-server -o jsonpath='{.spec.type}' 2>/dev/null)" = "ClusterIP" ] \
  || fail "argocd-server must be ClusterIP (no external exposure)"
if kubectl -n "$ARGOCD_NS" get ingress 2>/dev/null | grep -q .; then fail "ArgoCD ingress present (forbidden)"; fi

# ---- apply restricted project + application ----------------------------------
echo "### applying restricted AppProject + Application"
kubectl apply -f "$PROJ_MANIFEST" >/dev/null 2>&1 || fail "AppProject apply failed"
kubectl apply -f "$APP_MANIFEST" >/dev/null 2>&1 || fail "Application apply failed"

# ---- confirm manual-only (no automated block) --------------------------------
AUTO="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.spec.syncPolicy.automated}' 2>/dev/null)"
[ -z "$AUTO" ] || fail "auto-sync is configured on the Application (must be manual-only)"
DEST="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.spec.destination.namespace}' 2>/dev/null)"
[ "$DEST" = "$DEST_NS" ] || fail "Application destination is not $DEST_NS"
echo "  [OK] manual-only; destination $DEST_NS"

# ---- trigger ONE manual sync -------------------------------------------------
echo "### triggering manual sync"
kubectl -n "$ARGOCD_NS" annotate application "$APP" argocd.argoproj.io/refresh=hard --overwrite >/dev/null 2>&1 || true
sleep 5
kubectl -n "$ARGOCD_NS" patch application "$APP" --type merge -p \
  '{"operation":{"info":[{"name":"reason","value":"step56-nonprod-manual-sync"}],"initiatedBy":{"username":"nonprod-manual"},"sync":{"revision":"main","prune":false,"syncStrategy":{"apply":{"force":false}}}}}' \
  >/dev/null 2>&1 || fail "could not trigger manual sync"

# ---- wait for convergence ----------------------------------------------------
for i in $(seq 1 25); do
  s="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.status.sync.status}' 2>/dev/null)"
  h="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.status.health.status}' 2>/dev/null)"
  p="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.status.operationState.phase}' 2>/dev/null)"
  echo "  t=$i sync=$s health=$h op=$p"
  [ "$s" = "Synced" ] && [ "$h" = "Healthy" ] && break
  { [ "$p" = "Failed" ] || [ "$p" = "Error" ]; } && fail "manual sync operation $p"
  sleep 12
done
[ "$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{.status.sync.status}')" = "Synced" ] \
  || fail "Application did not reach Synced"

# ---- redacted report + safety confirmations ----------------------------------
echo "### collecting redacted sync report"
"$PY" scripts/run_nonproduction_argocd_manual_sync_report.py || fail "report generation / validation failed"

# resources only in the destination namespace (no production namespace touched)
NSES="$(kubectl -n "$ARGOCD_NS" get application "$APP" -o jsonpath='{range .status.resources[*]}{.namespace} {end}' 2>/dev/null)"
for ns in $NSES; do
  case "$ns" in *production*) fail "a synced resource targets a production namespace: $ns" ;; esac
  [ "$ns" = "default" ] && fail "a synced resource targets the default namespace"
  [ "$ns" = "kube-system" ] && fail "a synced resource targets kube-system"
done

echo "  [OK] manual sync complete; non-production destination only; no auto-sync/prune/selfHeal"
echo "NONPROD_ARGOCD_MANUAL_SYNC_RUN: PASS"
exit 0
