#!/usr/bin/env python3
"""Step 51.2A -- static workload security policy checker.

Reads the rendered manifests in .runtime/kubernetes-rendered/ (produced by
verify_helm_foundation.sh; rendered here as a fallback via local/docker helm if
absent) and verifies the restricted security baseline for every workload.

NO cluster connection, NO kubectl, NO helm install. Hard violations FAIL;
runtime-compatibility items from the inventory are reported as observations.

Marker: KUBERNETES_WORKLOAD_SECURITY_VERIFY: PASS | FAIL
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
INVENTORY = ROOT / "infra" / "kubernetes" / "workload-security-inventory.yaml"
HELM_IMAGE = "alpine/helm:3.16.3"

ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
FIRST_PARTY = {"application", "governance", "communication", "worker", "agent"}
WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}

failures: list[str] = []
passes: list[str] = []
observations: list[str] = []


def ok(msg: str) -> None:
    passes.append(msg)


def fail(env: str, kind: str, name: str, comp: str, field: str, reason: str) -> None:
    failures.append(f"[{env}] {kind}/{name} component={comp} field={field}: {reason}")


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
        if res.returncode != 0:
            print(f"  render failed ({env}): {res.stderr.strip()[:200]}")
            continue
        p = RENDER_DIR / f"{env}.yaml"
        p.write_text(res.stdout, encoding="utf-8")
        out.append(p)
    return out


def pod_spec(doc: dict) -> dict | None:
    try:
        return doc["spec"]["template"]["spec"]
    except (KeyError, TypeError):
        return None


def check_workload(env: str, doc: dict, inv_health: dict) -> None:
    kind = doc.get("kind", "")
    name = doc.get("metadata", {}).get("name", "?")
    labels = doc.get("metadata", {}).get("labels", {}) or {}
    comp = labels.get("app.kubernetes.io/name", name)
    ctype = labels.get("app.kubernetes.io/component", "")
    spec = pod_spec(doc)
    if spec is None:
        fail(env, kind, name, comp, "spec.template.spec", "missing pod spec")
        return

    # ---- pod-level securityContext ----
    psc = spec.get("securityContext", {}) or {}
    if psc.get("runAsNonRoot") is not True:
        fail(env, kind, name, comp, "securityContext.runAsNonRoot", "must be true")
    if psc.get("runAsUser") in (0, None):
        fail(
            env,
            kind,
            name,
            comp,
            "securityContext.runAsUser",
            f"must be non-zero (got {psc.get('runAsUser')})",
        )
    seccomp = (psc.get("seccompProfile") or {}).get("type")
    if seccomp != "RuntimeDefault":
        fail(
            env,
            kind,
            name,
            comp,
            "securityContext.seccompProfile.type",
            f"must be RuntimeDefault (got {seccomp})",
        )

    # ---- pod-level dangerous features ----
    if spec.get("automountServiceAccountToken") is not False:
        fail(env, kind, name, comp, "automountServiceAccountToken", "must be false at pod spec")
    for hostfield in ("hostNetwork", "hostPID", "hostIPC"):
        if spec.get(hostfield) is True:
            fail(env, kind, name, comp, hostfield, "must not be true")
    if "terminationGracePeriodSeconds" not in spec:
        fail(env, kind, name, comp, "terminationGracePeriodSeconds", "missing")

    # ---- volumes: no hostPath / docker socket ----
    for vol in spec.get("volumes", []) or []:
        if "hostPath" in vol:
            fail(env, kind, name, comp, "volumes.hostPath", "hostPath is forbidden")
        ed = vol.get("emptyDir")
        if ed is not None and "sizeLimit" not in ed:
            fail(
                env,
                kind,
                name,
                comp,
                f"volumes[{vol.get('name')}].emptyDir.sizeLimit",
                "missing sizeLimit",
            )

    # ---- containers ----
    containers = spec.get("containers", []) or []
    if not containers:
        fail(env, kind, name, comp, "containers", "no containers")
    for c in containers:
        csc = c.get("securityContext", {}) or {}
        if csc.get("allowPrivilegeEscalation") is not False:
            fail(env, kind, name, comp, "allowPrivilegeEscalation", "must be false")
        if csc.get("privileged") is True:
            fail(env, kind, name, comp, "privileged", "must not be true")
        caps = csc.get("capabilities", {}) or {}
        if "ALL" not in (caps.get("drop") or []):
            fail(env, kind, name, comp, "capabilities.drop", "must drop ALL")
        if caps.get("add"):
            fail(
                env,
                kind,
                name,
                comp,
                "capabilities.add",
                f"capability add forbidden ({caps.get('add')})",
            )
        # first-party workloads must have read-only root filesystem
        if ctype in FIRST_PARTY and csc.get("readOnlyRootFilesystem") is not True:
            fail(
                env, kind, name, comp, "readOnlyRootFilesystem", "first-party workload must be true"
            )
        # docker socket mount
        for vm in c.get("volumeMounts", []) or []:
            if "docker.sock" in str(vm.get("mountPath", "")):
                fail(env, kind, name, comp, "volumeMounts", "docker socket mount forbidden")
        # resources
        res = c.get("resources", {}) or {}
        for sect in ("requests", "limits"):
            for key in ("cpu", "memory"):
                if not (res.get(sect) or {}).get(key):
                    fail(env, kind, name, comp, f"resources.{sect}.{key}", "missing")
        # probes (first-party only)
        if ctype in FIRST_PARTY:
            if "livenessProbe" not in c:
                fail(env, kind, name, comp, "livenessProbe", "missing")
            if "readinessProbe" not in c:
                fail(env, kind, name, comp, "readinessProbe", "missing")
            # health path consistency with inventory
            want = inv_health.get(comp)
            got = ((c.get("readinessProbe") or {}).get("httpGet") or {}).get("path")
            if want and got and want != got:
                fail(
                    env,
                    kind,
                    name,
                    comp,
                    "readinessProbe.httpGet.path",
                    f"expected {want}, got {got}",
                )


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_WORKLOAD_SECURITY_VERIFY: FAIL")
        return 1

    inv = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    inv_health = {}
    for cname, c in inv.get("components", {}).items():
        # first-party health path comes from the foundation values (httpGet /health)
        if c.get("classification") in (
            "core_application",
            "governance_service",
            "communication_service",
            "worker",
            "agent",
        ):
            inv_health[cname] = "/health"

    n_workloads = 0
    for path in rendered:
        env = path.stem
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") in WORKLOAD_KINDS:
                n_workloads += 1
                check_workload(env, doc, inv_health)

    # runtime-compat observations (not failures)
    for cname, c in inv.get("components", {}).items():
        rc = c.get("runtimeCompatibility", {})
        if rc.get("status") == "requires_cluster_smoke":
            observations.append(f"{cname}: requires_cluster_smoke")

    print(
        f"=== Workload security: checked {n_workloads} workloads across {len(rendered)} environments ==="
    )
    if observations:
        print(
            f"  observations (runtime-compat, not failures): {len(observations)} components require cluster smoke"
        )
    if failures:
        print(f"  {len(failures)} violation(s):")
        for f in failures:
            print(f"    [FAIL] {f}")
        print("KUBERNETES_WORKLOAD_SECURITY_VERIFY: FAIL")
        return 1
    print(f"  [PASS] all {n_workloads} workloads satisfy the restricted security baseline")
    if observations:
        print("KUBERNETES_WORKLOAD_SECURITY_VERIFY: PASS (with runtime-compatibility observations)")
    else:
        print("KUBERNETES_WORKLOAD_SECURITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
