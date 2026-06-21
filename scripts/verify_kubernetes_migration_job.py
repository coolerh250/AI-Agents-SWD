#!/usr/bin/env python3
"""Step 51.2C2 -- migration Job verifier (rendered).

Asserts the migration Job renders only in dev/test, with a fixed shell-free
command, secretKeyRef-only DATABASE_URL, advisory-lock model, backoffLimit 0,
deadline/TTL, restricted security, automount off, and no Helm/ArgoCD hook --
and never renders in staging/production. No execution.

Marker: KUBERNETES_MIGRATION_JOB_VERIFY: PASS | FAIL
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
HELM_IMAGE = "alpine/helm:3.16.3"
ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
HOOK_KEYS = ("helm.sh/hook", "argocd.argoproj.io/hook", "argocd.argoproj.io/sync-wave")

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


def ensure_rendered() -> dict[str, Path]:
    existing = {p.stem: p for p in RENDER_DIR.glob("*.yaml")}
    if set(ENV_VALUES) <= set(existing):
        return {e: existing[e] for e in ENV_VALUES}
    base = _helm_base()
    if base is None:
        return {}
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for env, vf in ENV_VALUES.items():
        res = subprocess.run(
            base + ["template", "ai-agents-platform", CHART_REL, "-f", f"{CHART_REL}/{vf}"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if res.returncode == 0:
            p = RENDER_DIR / f"{env}.yaml"
            p.write_text(res.stdout, encoding="utf-8")
            out[env] = p
    return out


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def main() -> int:
    rendered = ensure_rendered()
    if not rendered:
        print("  [FAIL] no rendered manifests and no helm/docker to render them")
        print("KUBERNETES_MIGRATION_JOB_VERIFY: FAIL")
        return 1

    for env, path in rendered.items():
        all_docs = docs(path)
        jobs = [
            d
            for d in all_docs
            if d.get("kind") == "Job" and d["metadata"]["name"].endswith("-migration")
        ]
        if env in ("dev", "test"):
            if not jobs:
                bad(f"[{env}] expected a migration Job")
                continue
            ok(f"[{env}] migration Job rendered")
        else:
            if jobs:
                bad(f"[{env}] migration Job must NOT render")
            else:
                ok(f"[{env}] no migration Job (correct)")
            continue

        for j in jobs:
            meta = j.get("metadata", {})
            spec = j.get("spec", {})
            pod = spec.get("template", {}).get("spec", {})
            ann = meta.get("annotations", {}) or {}
            if any(k in ann for k in HOOK_KEYS):
                bad(f"[{env}] migration Job has a Helm/ArgoCD hook annotation")
            if spec.get("backoffLimit") != 0:
                bad(f"[{env}] migration backoffLimit must be 0")
            if not spec.get("activeDeadlineSeconds") or not spec.get("ttlSecondsAfterFinished"):
                bad(f"[{env}] migration Job missing deadline/TTL")
            if pod.get("automountServiceAccountToken") is not False:
                bad(f"[{env}] migration automountServiceAccountToken must be false")
            c = (pod.get("containers") or [{}])[0]
            cmd = list(c.get("command", [])) + list(c.get("args", []))
            if cmd != ["python", "scripts/k8s_apply_migrations.py"]:
                bad(f"[{env}] migration command not fixed: {cmd}")
            if any("-c" == x or "&&" in str(x) for x in cmd):
                bad(f"[{env}] migration command uses a shell construct")
            # DATABASE_URL only via secretKeyRef; AIAGENTS_BATCH_EXECUTE=false
            for e in c.get("env", []) or []:
                if e.get("name") == "DATABASE_URL" and "valueFrom" not in e:
                    bad(f"[{env}] DATABASE_URL must use secretKeyRef")
                if e.get("name") == "AIAGENTS_BATCH_EXECUTE" and str(e.get("value")) == "true":
                    bad(f"[{env}] migration execution must be disabled")
            csc = c.get("securityContext", {})
            if (
                csc.get("allowPrivilegeEscalation") is not False
                or csc.get("readOnlyRootFilesystem") is not True
            ):
                bad(f"[{env}] migration container security context not restricted")
            if "ALL" not in (csc.get("capabilities", {}).get("drop") or []):
                bad(f"[{env}] migration must drop ALL capabilities")

    # advisory lock model (source-level) + no Lease anywhere
    values = yaml.safe_load((ROOT / CHART_REL / "values.yaml").read_text(encoding="utf-8"))
    lock = values["batchJobs"]["migration"]["lock"]
    if not lock.get("required") or lock.get("mode") != "postgres_advisory_lock":
        bad("migration must require a postgres_advisory_lock")
    else:
        ok("migration uses required postgres advisory lock (no Kubernetes Lease)")
    for path in rendered.values():
        if any(d.get("kind") == "Lease" for d in docs(path)):
            bad("migration must not require a Kubernetes Lease")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_MIGRATION_JOB_VERIFY: FAIL")
        return 1
    print("KUBERNETES_MIGRATION_JOB_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
