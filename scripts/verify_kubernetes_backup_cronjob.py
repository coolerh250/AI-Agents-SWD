#!/usr/bin/env python3
"""Step 51.2C2 -- backup CronJob verifier (rendered).

Asserts the backup CronJob renders only in dev/test, is SUSPENDED with
scheduleEnabled=false and concurrencyPolicy=Forbid, uses secretKeyRef-only
database + encryption refs (no inline key), has a disabled artifact target
(never an active datastore PVC), deadline/history limits, no external egress,
and no Helm/ArgoCD hook -- and never renders in staging/production. No execution.

Marker: KUBERNETES_BACKUP_CRONJOB_VERIFY: PASS | FAIL
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


def ensure_rendered() -> dict[str, Path]:
    existing = {p.stem: p for p in RENDER_DIR.glob("*.yaml")}
    if set(ENV_VALUES) <= set(existing):
        return {e: existing[e] for e in ENV_VALUES}
    if shutil.which("helm"):
        base = ["helm"]
    elif shutil.which("docker"):
        base = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", HELM_IMAGE]
    else:
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
        print("KUBERNETES_BACKUP_CRONJOB_VERIFY: FAIL")
        return 1

    for env, path in rendered.items():
        crons = [
            d
            for d in docs(path)
            if d.get("kind") == "CronJob" and d["metadata"]["name"].endswith("-backup")
        ]
        if env in ("dev", "test"):
            if not crons:
                bad(f"[{env}] expected a backup CronJob")
                continue
            ok(f"[{env}] backup CronJob rendered")
        else:
            if crons:
                bad(f"[{env}] backup CronJob must NOT render")
            else:
                ok(f"[{env}] no backup CronJob (correct)")
            continue

        for cj in crons:
            spec = cj.get("spec", {})
            ann = cj.get("metadata", {}).get("annotations", {}) or {}
            if any(k in ann for k in HOOK_KEYS):
                bad(f"[{env}] backup CronJob has a Helm/ArgoCD hook annotation")
            if spec.get("suspend") is not True:
                bad(f"[{env}] backup CronJob must be suspended")
            if spec.get("concurrencyPolicy") != "Forbid":
                bad(f"[{env}] backup concurrencyPolicy must be Forbid")
            for lim in (
                "successfulJobsHistoryLimit",
                "failedJobsHistoryLimit",
                "startingDeadlineSeconds",
            ):
                if lim not in spec:
                    bad(f"[{env}] backup CronJob missing {lim}")
            jt = spec.get("jobTemplate", {}).get("spec", {})
            if (
                jt.get("backoffLimit") != 0
                or not jt.get("activeDeadlineSeconds")
                or not jt.get("ttlSecondsAfterFinished")
            ):
                bad(f"[{env}] backup jobTemplate missing backoffLimit=0/deadline/TTL")
            pod = jt.get("template", {}).get("spec", {})
            if pod.get("automountServiceAccountToken") is not False:
                bad(f"[{env}] backup automountServiceAccountToken must be false")
            c = (pod.get("containers") or [{}])[0]
            cmd = list(c.get("command", [])) + list(c.get("args", []))
            if cmd != ["python", "scripts/k8s_encrypted_backup.py"]:
                bad(f"[{env}] backup command not fixed: {cmd}")
            seen_secret_env = set()
            for e in c.get("env", []) or []:
                if e.get("name") in ("DATABASE_URL", "BACKUP_ENCRYPTION_KEY"):
                    if "valueFrom" not in e:
                        bad(f"[{env}] {e.get('name')} must use secretKeyRef (no inline value)")
                    else:
                        seen_secret_env.add(e["name"])
                if e.get("name") == "AIAGENTS_BATCH_EXECUTE" and str(e.get("value")) == "true":
                    bad(f"[{env}] backup schedule/execution must be disabled")
            if {"DATABASE_URL", "BACKUP_ENCRYPTION_KEY"} - seen_secret_env:
                bad(f"[{env}] backup must reference DB + encryption secrets")
            # no external egress / cloud target in the cronjob env
            for e in c.get("env", []) or []:
                val = str(e.get("value", ""))
                if any(s in val for s in ("s3://", "gs://", "https://", "http://")):
                    bad(f"[{env}] backup env must not contain a real endpoint: {e.get('name')}")

    # artifact target disabled + not an active datastore PVC (source-level)
    values = yaml.safe_load((ROOT / CHART_REL / "values.yaml").read_text(encoding="utf-8"))
    target = values["batchJobs"]["backup"]["target"]
    if target["strategy"] != "disabled" or target.get("externalObjectStoreEnabled") is not False:
        bad("backup artifact target must be a disabled placeholder")
    elif target.get("existingClaim") in ("postgres-data", "redis-data"):
        bad("backup target must not reuse an active datastore PVC")
    else:
        ok("backup artifact target disabled; not an active datastore PVC")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("KUBERNETES_BACKUP_CRONJOB_VERIFY: FAIL")
        return 1
    print("KUBERNETES_BACKUP_CRONJOB_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
