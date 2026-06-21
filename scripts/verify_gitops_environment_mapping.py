#!/usr/bin/env python3
"""Step 51.3 -- GitOps environment mapping verifier (source-level).

Asserts gitops-environments.yaml matches the Application manifests and the Helm
values files, that dev/test are active but auto-sync-disabled, staging/production
are inactive, production is disabled and uses the prod-placeholder values, and the
production values stay fail-closed. No cluster, no argocd CLI.

Marker: GITOPS_ENVIRONMENT_MAPPING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def load(rel: str, base: Path = GITOPS) -> dict:
    return yaml.safe_load((base / rel).read_text(encoding="utf-8"))


def main() -> int:
    cat = load("gitops-environments.yaml")
    envs = cat["environments"]

    # 1. catalog source matches chart
    if cat["source"]["chartPath"] != "infra/kubernetes/charts/ai-agents-platform":
        bad("catalog chartPath mismatch")
    if cat.get("project") != "ai-agents-platform":
        bad("catalog project mismatch")

    # 2. every env: values file exists + Application manifest matches valuesFile
    for env, e in envs.items():
        vf = e["valuesFile"]
        if not (CHART / vf).is_file():
            bad(f"{env}: values file {vf} missing")
        app_rel = e.get("applicationFile")
        if app_rel:
            app = load(app_rel)
            got = app.get("spec", {}).get("source", {}).get("helm", {}).get("valueFiles", [])
            if got != [vf]:
                bad(f"{env}: Application valueFiles {got} != catalog {vf}")
        if e.get("automatedSync") is not False:
            bad(f"{env}: automatedSync must be false")
        if e.get("prune") not in (False, None):
            bad(f"{env}: prune must be false")
        if e.get("selfHeal") not in (False, None):
            bad(f"{env}: selfHeal must be false")
    if not failures:
        ok(
            f"all {len(envs)} environments map to existing values files + matching Applications, no auto-sync"
        )

    # 3. active / inactive
    if not (envs["dev"]["active"] and envs["test"]["active"]):
        bad("dev + test must be active in the catalog")
    if envs["staging-placeholder"]["active"] or envs["production-placeholder"]["active"]:
        bad("staging/production placeholders must be inactive")
    if not envs["production-placeholder"].get("disabled"):
        bad("production placeholder must be disabled=true")
    else:
        ok("dev/test active; staging/production inactive; production disabled")

    # 4. production uses prod-placeholder values + production:true
    prod = envs["production-placeholder"]
    if prod["valuesFile"] != "values-prod-placeholder.yaml":
        bad("production must use values-prod-placeholder.yaml")
    if prod.get("production") is not True:
        bad("production env must be marked production:true")
    # no env uses the wrong values file
    for env in ("dev", "test"):
        if "prod" in envs[env]["valuesFile"]:
            bad(f"{env} must not use production values")
    if not [f for f in failures if "production" in f or "values" in f]:
        ok("production uses prod-placeholder values; dev/test never use prod values")

    # 5. production values fail closed (parse merged prod values)
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((CHART / "values-prod-placeholder.yaml").read_text(encoding="utf-8"))

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out

    pv = merge(base, over)
    if pv["global"]["realDeployEnabled"] is not False:
        bad("production realDeployEnabled must be false")
    if pv["platform"]["adminConsole"]["operatorActionsEnabled"] is not False:
        bad("production operator actions must be disabled")
    if pv["components"]["postgres"]["enabled"] or pv["components"]["redis"]["enabled"]:
        bad("production must not enable internal datastores (no generated PVC)")
    if pv["networkPolicy"]["externalEgress"]["enabled"] is not False:
        bad("production external egress must be disabled")
    bj = pv["batchJobs"]
    if (
        bj["migration"]["renderTemplate"]
        or bj["backup"]["renderTemplate"]
        or bj["restore"]["renderTemplate"]
    ):
        bad("production must not render any batch job")
    if not [f for f in failures if "production" in f]:
        ok("production values fail closed (no deploy/PVC/egress/batch/operator actions)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("GITOPS_ENVIRONMENT_MAPPING_VERIFY: FAIL")
        return 1
    print("GITOPS_ENVIRONMENT_MAPPING_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
