#!/usr/bin/env python3
"""Step 51.2A -- Kubernetes RBAC safety checker.

Asserts that the rendered manifests and the RBAC safety catalog contain NO
privilege grants: no Role/ClusterRole/binding, no wildcard/secret/deployment/job
permissions, no pods/exec, ServiceAccount + Pod token automount disabled.

NO cluster connection, NO kubectl, NO helm install.

Marker: KUBERNETES_RBAC_SAFETY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_REL = "infra/kubernetes/charts/ai-agents-platform"
RENDER_DIR = ROOT / ".runtime" / "kubernetes-rendered"
CATALOG = ROOT / "infra" / "kubernetes" / "rbac-safety-catalog.yaml"
HELM_IMAGE = "alpine/helm:3.16.3"

ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
RBAC_KINDS = {"Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"}

failures: list[str] = []
passes: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)
    print(f"  [PASS] {msg}")


def bad(msg: str) -> None:
    failures.append(msg)
    print(f"  [FAIL] {msg}")


def ensure_rendered() -> list[Path]:
    existing = sorted(RENDER_DIR.glob("*.yaml"))
    if existing:
        return existing
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    if shutil.which("helm"):
        base = ["helm"]
    elif shutil.which("docker"):
        base = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", HELM_IMAGE]
    else:
        return []
    out: list[Path] = []
    for env, vf in ENV_VALUES.items():
        cmd = base + ["template", "ai-agents-platform", CHART_REL, "-f", f"{CHART_REL}/{vf}"]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if res.returncode == 0:
            p = RENDER_DIR / f"{env}.yaml"
            p.write_text(res.stdout, encoding="utf-8")
            out.append(p)
    return out


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_RBAC_SAFETY_VERIFY: FAIL")
        return 1

    print("=== Rendered manifest RBAC scan ===")
    rbac_objects = 0
    sa_count = 0
    pod_automount_bad = 0
    sa_automount_bad = 0
    for path in rendered:
        env = path.stem
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind", "")
            name = doc.get("metadata", {}).get("name", "?")
            if kind in RBAC_KINDS:
                rbac_objects += 1
                bad(f"[{env}] RBAC object present: {kind}/{name} (none expected this stage)")
            if kind == "ServiceAccount":
                sa_count += 1
                if doc.get("automountServiceAccountToken") is not False:
                    sa_automount_bad += 1
                    bad(f"[{env}] ServiceAccount/{name} automountServiceAccountToken must be false")
            if kind in ("Deployment", "StatefulSet", "DaemonSet"):
                spec = (((doc.get("spec") or {}).get("template") or {}).get("spec")) or {}
                if spec.get("automountServiceAccountToken") is not False:
                    pod_automount_bad += 1
                    bad(f"[{env}] {kind}/{name} pod automountServiceAccountToken must be false")

    if rbac_objects == 0:
        ok("no Role/RoleBinding/ClusterRole/ClusterRoleBinding rendered")
    if sa_count and sa_automount_bad == 0:
        ok(f"all {sa_count} ServiceAccounts set automountServiceAccountToken=false")
    if pod_automount_bad == 0:
        ok("all workloads set pod automountServiceAccountToken=false")

    # ---- RBAC safety catalog assertions ----
    print("=== RBAC safety catalog ===")
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    rbac = cat.get("rbac", {})
    flags = [
        "clusterRolesAllowed",
        "clusterRoleBindingsAllowed",
        "wildcardPermissionsAllowed",
        "secretReadPermissionsAllowed",
        "deploymentMutationPermissionsAllowed",
        "jobCreationPermissionsAllowed",
        "podsExecAllowed",
        "podsPortForwardAllowed",
    ]
    for fl in flags:
        if rbac.get(fl) is not False:
            bad(f"rbac.{fl} must be false")
    if all(rbac.get(fl) is False for fl in flags):
        ok(
            "RBAC catalog forbids cluster roles / wildcard / secret / deploy / job / exec / portforward"
        )
    for counter in (
        "rolesCreatedThisStage",
        "roleBindingsCreatedThisStage",
        "clusterRolesCreatedThisStage",
        "clusterRoleBindingsCreatedThisStage",
    ):
        if rbac.get(counter) != 0:
            bad(f"rbac.{counter} must be 0 (no RBAC objects created this stage)")

    comps = cat.get("components", {})
    if not comps:
        bad("RBAC catalog has no components")
    unresolved = [n for n, c in comps.items() if c.get("kubernetesApiRequired") not in (False,)]
    if unresolved:
        bad(f"components claim Kubernetes API access without deferral: {unresolved}")
    else:
        ok(f"all {len(comps)} components: kubernetesApiRequired=false")
    if cat.get("unresolvedKubernetesApiNeeds"):
        print(f"  [note] unresolvedKubernetesApiNeeds: {cat['unresolvedKubernetesApiNeeds']}")
    else:
        ok("no unresolved Kubernetes API needs")

    total = len(passes) + len(failures)
    print(f"\n=== Summary: {len(passes)}/{total} checks passed ===")
    if failures:
        print("KUBERNETES_RBAC_SAFETY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_RBAC_SAFETY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
