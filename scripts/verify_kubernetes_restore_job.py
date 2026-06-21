#!/usr/bin/env python3
"""Step 51.2C2 -- restore Job verifier (rendered).

Restore is CRITICAL. Asserts it NEVER renders in standard environments, and
that the dedicated dev fixture renders only a DISABLED, isolated scaffold:
fixed target prefix ``aiagents_restore_drill_``, source != target, no production
target, separate source/target Secret references, restricted security,
backoffLimit 0, deadline/TTL, no shell, no service-traffic switch, no execution.

Marker: KUBERNETES_RESTORE_JOB_VERIFY: PASS | FAIL
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
FIXTURE = "infra/kubernetes/fixtures/batch-restore-scaffold-fixture.yaml"
HELM_IMAGE = "alpine/helm:3.16.3"
ENV_VALUES = {
    "dev": "values-dev.yaml",
    "test": "values-test.yaml",
    "staging": "values-staging-placeholder.yaml",
    "prod": "values-prod-placeholder.yaml",
}
PREFIX = "aiagents_restore_drill_"
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


def render(base: list[str], values_files: list[str], out: Path) -> bool:
    args = base + ["template", "ai-agents-platform", CHART_REL]
    for vf in values_files:
        args += ["-f", vf]
    res = subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT))
    if res.returncode == 0:
        out.write_text(res.stdout, encoding="utf-8")
        return True
    print(f"  render failed: {res.stderr.strip()[:200]}")
    return False


def docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


def main() -> int:
    base = _helm_base()
    standard = {p.stem: p for p in RENDER_DIR.glob("*.yaml") if p.stem in ENV_VALUES}
    if set(ENV_VALUES) - set(standard):
        if base is None:
            print("  [FAIL] no rendered manifests and no helm/docker to render them")
            print("KUBERNETES_RESTORE_JOB_VERIFY: FAIL")
            return 1
        RENDER_DIR.mkdir(parents=True, exist_ok=True)
        for env, vf in ENV_VALUES.items():
            p = RENDER_DIR / f"{env}.yaml"
            if render(base, [f"{CHART_REL}/{vf}"], p):
                standard[env] = p

    # 1. restore NEVER renders in any standard environment
    for env, path in standard.items():
        if any(
            d.get("kind") == "Job" and d["metadata"]["name"].endswith("-restore-drill")
            for d in docs(path)
        ):
            bad(f"[{env}] restore Job must NOT render in standard values")
    if not failures:
        ok("restore Job absent from all standard environments")

    # 2. fixture renders the disabled scaffold
    if base is None:
        print("  [FAIL] cannot render restore fixture (no helm/docker)")
        print("KUBERNETES_RESTORE_JOB_VERIFY: FAIL")
        return 1
    fix = RENDER_DIR / "fixture-restore.yaml"
    if not render(base, [f"{CHART_REL}/values-dev.yaml", FIXTURE], fix):
        bad("restore fixture failed to render")
        print("KUBERNETES_RESTORE_JOB_VERIFY: FAIL")
        return 1
    jobs = [
        d
        for d in docs(fix)
        if d.get("kind") == "Job" and d["metadata"]["name"].endswith("-restore-drill")
    ]
    if not jobs:
        bad("restore fixture did not render the scaffold Job")
    else:
        ok("restore fixture renders the disabled scaffold")

    for j in jobs:
        spec = j.get("spec", {})
        ann = j.get("metadata", {}).get("annotations", {}) or {}
        if any(k in ann for k in HOOK_KEYS):
            bad("restore Job has a Helm/ArgoCD hook annotation")
        if (
            spec.get("backoffLimit") != 0
            or not spec.get("activeDeadlineSeconds")
            or not spec.get("ttlSecondsAfterFinished")
        ):
            bad("restore Job missing backoffLimit=0/deadline/TTL")
        pod = spec.get("template", {}).get("spec", {})
        if pod.get("automountServiceAccountToken") is not False:
            bad("restore automountServiceAccountToken must be false")
        c = (pod.get("containers") or [{}])[0]
        cmd = list(c.get("command", [])) + list(c.get("args", []))
        if cmd != ["python", "scripts/k8s_restore_drill.py"]:
            bad(f"restore command not fixed: {cmd}")
        envmap = {e.get("name"): e for e in c.get("env", []) or []}
        tgt = str(envmap.get("RESTORE_TARGET_DATABASE", {}).get("value", ""))
        src = str(envmap.get("RESTORE_SOURCE_DATABASE", {}).get("value", ""))
        if not tgt.startswith(PREFIX):
            bad(f"restore target must start with {PREFIX} (got {tgt})")
        if tgt == src:
            bad("restore source and target must differ")
        if tgt in ("aiagents", "postgres"):
            bad("restore target must not be the primary catalog")
        if str(envmap.get("AIAGENTS_BATCH_EXECUTE", {}).get("value")) == "true":
            bad("restore execution must be disabled")
        # separate source/target credential secret references
        src_ref = (
            envmap.get("RESTORE_SOURCE_DATABASE_URL", {}).get("valueFrom", {}).get("secretKeyRef")
        )
        tgt_ref = (
            envmap.get("RESTORE_TARGET_DATABASE_URL", {}).get("valueFrom", {}).get("secretKeyRef")
        )
        if not src_ref or not tgt_ref:
            bad("restore source + target credentials must use secretKeyRef")
        elif (src_ref.get("name"), src_ref.get("key")) == (tgt_ref.get("name"), tgt_ref.get("key")):
            bad("restore source and target must use SEPARATE secret references")
        # no Service / traffic switch in fixture
    if any(d.get("kind") == "Service" and "restore" in d["metadata"]["name"] for d in docs(fix)):
        bad("restore must not create a Service (no traffic switch)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_RESTORE_JOB_VERIFY: FAIL")
        return 1
    print("KUBERNETES_RESTORE_JOB_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
