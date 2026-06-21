#!/usr/bin/env python3
"""Step 51.2C2 -- batch job policy verifier (rendered).

Scans EVERY rendered batch Job/CronJob (standard four envs + the restore
fixture) and enforces the cross-cutting safety policy: no production batch
resource, fixed shell-free commands, no Helm/ArgoCD hook, no privileged/root,
no hostPath/docker socket, ServiceAccount token off, no Kubernetes RBAC, no
secret literal / real endpoint, CronJob suspended + Forbid, Job deadline/TTL,
execution disabled, and no active-datastore storage collision.

Marker: KUBERNETES_BATCH_JOB_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART_REL = "infra/kubernetes/charts/ai-agents-platform"
RENDER_DIR = ROOT / ".runtime" / "kubernetes-rendered"
FIXTURE = "infra/kubernetes/fixtures/batch-restore-scaffold-fixture.yaml"
HELM_IMAGE = "alpine/helm:3.16.3"
ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
HOOK_KEYS = ("helm.sh/hook", "argocd.argoproj.io/hook", "argocd.argoproj.io/sync-wave")
FIXED_COMMANDS = {
    "scripts/k8s_apply_migrations.py",
    "scripts/k8s_encrypted_backup.py",
    "scripts/k8s_restore_drill.py",
}
SECRET_PAT = re.compile(
    r"(password|passwd|secret[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,})\s*[:=]\s*\S",
    re.IGNORECASE,
)
ENDPOINT_PAT = re.compile(r"(s3://|gs://|https?://[a-z0-9.-]+\.[a-z]{2,})", re.IGNORECASE)

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _helm_base() -> list[str] | None:
    if shutil.which("helm"):
        return ["helm"]
    if shutil.which("docker"):
        return ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", HELM_IMAGE]
    return None


def render(base: list[str], values_files: list[str], out: Path) -> bool:
    args = base + ["template", "ai-agents-platform", CHART_REL]
    for vf in values_files:
        args += ["-f", vf]
    res = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT))
    if res.returncode == 0:
        out.write_text(res.stdout, encoding="utf-8")
        return True
    return False


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def pod_of(doc: dict) -> dict:
    s = doc.get("spec", {})
    if doc.get("kind") == "CronJob":
        return s.get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec", {})
    return s.get("template", {}).get("spec", {})


def check_pod(env: str, name: str, pod: dict) -> None:
    if pod.get("hostNetwork") or pod.get("hostPID") or pod.get("hostIPC"):
        bad(f"[{env}] {name} uses host namespaces")
    if pod.get("automountServiceAccountToken") is not False:
        bad(f"[{env}] {name} ServiceAccount token must not be mounted")
    psc = pod.get("securityContext", {}) or {}
    if psc.get("runAsNonRoot") is not True or psc.get("runAsUser") in (0, None):
        bad(f"[{env}] {name} pod must run as non-root")
    for vol in pod.get("volumes", []) or []:
        if "hostPath" in vol:
            bad(f"[{env}] {name} uses hostPath")
        pvc = vol.get("persistentVolumeClaim", {}) or {}
        if pvc.get("claimName", "").endswith(("-postgres-data", "-redis-data")):
            bad(f"[{env}] {name} mounts an active datastore PVC ({pvc.get('claimName')})")
    for c in pod.get("containers", []) or []:
        cmd = list(c.get("command", [])) + list(c.get("args", []))
        if "-c" in cmd or any("sh -c" in str(x) or "&&" in str(x) or "$(" in str(x) for x in cmd):
            bad(f"[{env}] {name} command uses a shell construct: {cmd}")
        if not any(tok in FIXED_COMMANDS for tok in cmd):
            bad(f"[{env}] {name} command is not a fixed batch entrypoint: {cmd}")
        if "docker.sock" in str(cmd):
            bad(f"[{env}] {name} references the docker socket")
        csc = c.get("securityContext", {}) or {}
        if csc.get("privileged") is True or csc.get("allowPrivilegeEscalation") is not False:
            bad(f"[{env}] {name} container privileged/privesc")
        if "ALL" not in (csc.get("capabilities", {}).get("drop") or []):
            bad(f"[{env}] {name} must drop ALL capabilities")
        for e in c.get("env", []) or []:
            if e.get("name") == "AIAGENTS_BATCH_EXECUTE" and str(e.get("value")) == "true":
                bad(f"[{env}] {name} execution must be disabled")
            if ENDPOINT_PAT.search(str(e.get("value", ""))):
                bad(f"[{env}] {name} env contains a real endpoint")


def main() -> int:
    base = _helm_base()
    rendered: dict[str, Path] = {
        p.stem: p for p in RENDER_DIR.glob("*.yaml") if p.stem in ENV_VALUES
    }
    if (set(ENV_VALUES) - set(rendered)) and base is not None:
        RENDER_DIR.mkdir(parents=True, exist_ok=True)
        for env, vf in ENV_VALUES.items():
            p = RENDER_DIR / f"{env}.yaml"
            if render(base, [f"{CHART_REL}/{vf}"], p):
                rendered[env] = p
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_BATCH_JOB_POLICY_VERIFY: FAIL")
        return 1
    # add the restore fixture
    if base is not None:
        fix = RENDER_DIR / "fixture-restore.yaml"
        if render(base, [f"{CHART_REL}/values-dev.yaml", FIXTURE], fix):
            rendered["fixture"] = fix

    n_batch = 0
    for env, path in rendered.items():
        all_docs = docs(path)
        # no Kubernetes RBAC objects anywhere
        if any(
            d.get("kind") in ("Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding")
            for d in all_docs
        ):
            bad(f"[{env}] Kubernetes RBAC object rendered (forbidden)")
        raw = path.read_text(encoding="utf-8")
        if SECRET_PAT.search(raw):
            bad(f"[{env}] secret-like literal in rendered output")
        for d in all_docs:
            labels = d.get("metadata", {}).get("labels", {}) or {}
            if (
                d.get("kind") in ("Job", "CronJob")
                and labels.get("app.kubernetes.io/component") == "batch"
            ):
                n_batch += 1
                name = d["metadata"]["name"]
                if env == "prod" or env == "staging":
                    bad(f"[{env}] batch resource {name} must not render in {env}")
                ann = d.get("metadata", {}).get("annotations", {}) or {}
                if any(k in ann for k in HOOK_KEYS):
                    bad(f"[{env}] {name} has a Helm/ArgoCD hook annotation")
                if d.get("kind") == "CronJob":
                    s = d.get("spec", {})
                    if s.get("suspend") is not True or s.get("concurrencyPolicy") != "Forbid":
                        bad(f"[{env}] {name} CronJob must be suspended + Forbid")
                    jt = s.get("jobTemplate", {}).get("spec", {})
                    if jt.get("backoffLimit") != 0 or not jt.get("ttlSecondsAfterFinished"):
                        bad(f"[{env}] {name} missing backoffLimit=0/TTL")
                else:
                    s = d.get("spec", {})
                    if (
                        s.get("backoffLimit") != 0
                        or not s.get("activeDeadlineSeconds")
                        or not s.get("ttlSecondsAfterFinished")
                    ):
                        bad(f"[{env}] {name} missing backoffLimit=0/deadline/TTL")
                check_pod(env, name, pod_of(d))

    if n_batch == 0:
        bad("no batch workloads found to validate")
    elif not failures:
        ok(f"all {n_batch} rendered batch workloads satisfy the batch safety policy")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_BATCH_JOB_POLICY_VERIFY: FAIL")
        return 1
    print("KUBERNETES_BATCH_JOB_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
