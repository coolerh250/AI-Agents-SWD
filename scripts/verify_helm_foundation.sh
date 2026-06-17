#!/usr/bin/env bash
# Step 51.1 -- verify the multi-environment Helm FOUNDATION for ai-agents-platform.
#
# Lints + renders the chart for dev / test / staging-placeholder /
# production-placeholder and scans the rendered output for safety violations.
# NO cluster connection, NO kubectl, NO helm install/upgrade, NO ArgoCD.
#
# Helm tooling: prefers a local `helm`; otherwise runs a PINNED official Helm
# container image via docker. Never curl|sh. If neither is available the script
# reports an environment limitation and FAILS (markers require real lint/render).
#
# Marker: HELM_FOUNDATION_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

CHART="infra/kubernetes/charts/ai-agents-platform"
RENDER_DIR=".runtime/kubernetes-rendered"
HELM_IMAGE="${HELM_IMAGE:-alpine/helm:3.16.3}"
RELEASE="ai-agents-platform"

PASS=0
FAIL=0
ok()   { PASS=$((PASS+1)); echo "  [PASS] $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  [FAIL] $1"; }

declare -A ENV_FILES=(
  [dev]="$CHART/values-dev.yaml"
  [test]="$CHART/values-test.yaml"
  [staging]="$CHART/values-staging-placeholder.yaml"
  [prod]="$CHART/values-prod-placeholder.yaml"
)

# ---- resolve helm ----
HELM_MODE=""
helm_run() { :; }
if command -v helm >/dev/null 2>&1; then
  HELM_MODE="local"
  helm_run() { helm "$@"; }
elif command -v docker >/dev/null 2>&1; then
  HELM_MODE="docker:$HELM_IMAGE"
  helm_run() { docker run --rm -v "$PWD":/work -w /work "$HELM_IMAGE" "$@"; }
else
  echo "  [FAIL] no helm and no docker available -- environment limitation"
  echo "HELM_FOUNDATION_VERIFY: FAIL"
  exit 1
fi
echo "=== Helm tooling: $HELM_MODE ==="

# ---- Check 1-5: chart structure ----
echo "=== Check 1-5: chart structure ==="
for f in Chart.yaml values.yaml values.schema.json values-dev.yaml \
         values-test.yaml values-staging-placeholder.yaml values-prod-placeholder.yaml \
         component-catalog.yaml templates/_helpers.tpl templates/deployments.yaml \
         templates/services.yaml templates/configmaps.yaml templates/serviceaccounts.yaml \
         templates/validate-values.yaml templates/NOTES.txt \
         templates/_security_helpers.tpl templates/networkpolicies.yaml \
         templates/persistentvolumeclaims.yaml; do
  if [ -f "$CHART/$f" ]; then ok "present: $f"; else bad "missing: $f"; fi
done
# forbidden Step 51.2C2+ template files must NOT exist yet
for f in templates/migration-job.yaml templates/backup-cronjob.yaml \
         templates/horizontalpodautoscalers.yaml templates/poddisruptionbudgets.yaml; do
  if [ -e "$CHART/$f" ]; then bad "Step 51.2C2 file present too early: $f"; else ok "correctly absent: $f"; fi
done
if [ -e "$CHART/../../charts/ai-agents-platform/argocd" ] || [ -e "infra/kubernetes/argocd" ]; then
  bad "argocd/ present too early (Step 51.3)"
else
  ok "argocd/ correctly absent"
fi

# ---- Check 6: helm lint (all envs, strict) ----
echo "=== Check 6: helm lint ==="
for env in dev test staging prod; do
  if helm_run lint "$CHART" --strict -f "${ENV_FILES[$env]}" >/tmp/helm_lint_$env.txt 2>&1; then
    ok "helm lint ($env)"
  else
    bad "helm lint ($env)"; sed 's/^/      /' /tmp/helm_lint_$env.txt
  fi
done

# ---- Check 7-10: helm template render ----
echo "=== Check 7-10: helm template render ==="
rm -rf "$RENDER_DIR"
mkdir -p "$RENDER_DIR"
declare -A RENDERED=()
for env in dev test staging prod; do
  out="$RENDER_DIR/$env.yaml"
  if helm_run template "$RELEASE" "$CHART" -f "${ENV_FILES[$env]}" >"$out" 2>/tmp/helm_tpl_$env.txt; then
    if [ -s "$out" ]; then ok "helm template ($env) -> $(grep -c '^kind:' "$out") objects"; RENDERED[$env]="$out"; else bad "helm template ($env) empty"; fi
  else
    bad "helm template ($env)"; sed 's/^/      /' /tmp/helm_tpl_$env.txt
  fi
done

ALL_RENDERED="/tmp/helm_all_rendered.yaml"
cat "$RENDER_DIR"/*.yaml > "$ALL_RENDERED" 2>/dev/null || true

# ---- Check 11: no latest image ----
echo "=== Check 11: no :latest image ==="
if grep -nE 'image:\s*\S*:latest(\s|$|")' "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered output uses :latest image"; grep -nE 'image:\s*\S*:latest' "$ALL_RENDERED" | sed 's/^/      /'
else
  ok "no :latest image in any render"
fi

# ---- Check 12-13: no inline secret / real credential ----
echo "=== Check 12-13: no inline secret / credential ==="
if grep -nE 'kind:\s*Secret' "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered output contains a Secret resource (chart must not create Secrets)"
else
  ok "no Secret resource rendered"
fi
SECRET_PAT='(password|passwd|api[_-]?key|secret[_-]?key|aws_secret|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]+)\s*[:=]\s*[^"'"'"' ]'
if grep -nEi "$SECRET_PAT" "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered output may contain an inline secret value"; grep -nEi "$SECRET_PAT" "$ALL_RENDERED" | sed 's/^/      /'
else
  ok "no inline secret-like values in render (secretKeyRef references only)"
fi

# ---- Check 14: no NodePort / LoadBalancer ----
echo "=== Check 14: services internal-only ==="
if grep -nE 'type:\s*(NodePort|LoadBalancer)' "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered Service uses NodePort/LoadBalancer"
else
  ok "all Services are ClusterIP (internal-only)"
fi
if grep -nE 'kind:\s*Ingress' "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered output contains an Ingress"
else
  ok "no Ingress rendered"
fi

# ---- Check 15: no ClusterRole / ClusterRoleBinding / Role / RoleBinding ----
echo "=== Check 15: no RBAC objects ==="
if grep -nE 'kind:\s*(ClusterRole|ClusterRoleBinding|Role|RoleBinding)\b' "$ALL_RENDERED" >/dev/null 2>&1; then
  bad "rendered output contains RBAC objects (deferred to Step 51.2)"
else
  ok "no Role/RoleBinding/ClusterRole/ClusterRoleBinding rendered"
fi

# ---- Check 16: no production deploy enabled ----
echo "=== Check 16: production not deployable ==="
if [ -n "${RENDERED[prod]:-}" ]; then
  if grep -nE 'REAL_DEPLOY_ENABLED:\s*"true"' "${RENDERED[prod]}" >/dev/null 2>&1; then
    bad "production render has REAL_DEPLOY_ENABLED=true"
  else
    ok "production render keeps REAL_DEPLOY_ENABLED=false"
  fi
  if grep -nE 'PRODUCTION:\s*"true"' "${RENDERED[prod]}" >/dev/null 2>&1; then
    ok "production render marks PRODUCTION=true (placeholder shape)"
  else
    bad "production render missing PRODUCTION=true"
  fi
fi
# fail-closed: a deliberately bad production override must FAIL to render
echo "=== Check 16b: fail-closed enforcement ==="
if helm_run template "$RELEASE" "$CHART" -f "${ENV_FILES[prod]}" \
     --set platform.adminConsole.operatorActionsEnabled=true >/tmp/helm_failclosed.txt 2>&1; then
  bad "fail-closed broken: production + operatorActions rendered without error"
else
  ok "fail-closed: production + operatorActions correctly rejected"
fi
if helm_run template "$RELEASE" "$CHART" -f "${ENV_FILES[dev]}" \
     --set global.realDeployEnabled=true >/tmp/helm_failclosed2.txt 2>&1; then
  bad "fail-closed broken: realDeployEnabled=true rendered without error"
else
  ok "fail-closed: realDeployEnabled=true correctly rejected"
fi

# ---- Check 17: no rendered files tracked by Git ----
echo "=== Check 17: render output untracked ==="
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  bad "rendered output is tracked by Git"
else
  ok "rendered output not tracked by Git"
fi
if git check-ignore -q "$RENDER_DIR/dev.yaml" 2>/dev/null; then
  ok "render dir is gitignored"
else
  bad "render dir is NOT gitignored"
fi

# ---- Check 18: no cluster command executed ----
# Scan only non-comment lines so the header doc ("NO helm install/upgrade")
# does not self-trigger.
echo "=== Check 18: no cluster mutation commands ==="
if grep -vE '^[[:space:]]*#' "$0" \
     | grep -vE 'ok |bad ' \
     | grep -nE '(kubectl|helm_run|helm)[[:space:]]+(apply|install|upgrade|delete|create)\b' >/dev/null 2>&1; then
  bad "this verifier contains a cluster mutation command"
else
  ok "verifier performs no cluster-state-changing commands"
fi

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -ne 0 ]; then
  echo "HELM_FOUNDATION_VERIFY: FAIL"
  exit 1
fi
echo "HELM_FOUNDATION_VERIFY: PASS"
