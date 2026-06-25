#!/usr/bin/env python3
"""Step 55 -- non-production namespace plan verifier (static).

Marker: NONPROD_NAMESPACE_PLAN_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "infra" / "kubernetes" / "nonproduction-namespace-plan.yaml"

FORBIDDEN = {"default", "kube-system", "argocd", "production", "prod", "staging-prod"}
REQUIRED_LABELS = {
    "aiagents.openai.local/environment": "non-production",
    "aiagents.openai.local/purpose": "runtime-smoke",
    "aiagents.openai.local/production": "false",
}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not PLAN.is_file():
        bad("missing nonproduction-namespace-plan.yaml")
        print("NONPROD_NAMESPACE_PLAN_VERIFY: FAIL")
        return 1
    plan = (yaml.safe_load(PLAN.read_text(encoding="utf-8")) or {}).get(
        "nonProductionNamespacePlan", {}
    )

    ns = str(plan.get("namespace", ""))
    if ns in FORBIDDEN or "prod" in ns.lower() or not ns:
        bad(f"namespace not safe non-production: {ns!r}")
    else:
        ok(f"namespace is non-production: {ns}")

    if not plan.get("namespace", "").startswith("aiagents-smoke"):
        bad("namespace should be an aiagents-smoke-* namespace")
    else:
        ok("namespace uses the aiagents-smoke-* convention")

    labels = plan.get("labels", {})
    for k, v in REQUIRED_LABELS.items():
        if str(labels.get(k)) != v:
            bad(f"missing/incorrect label {k}={v}")
    if not [f for f in failures if "label" in f]:
        ok("non-production labels present (environment / purpose / production=false)")

    forbidden = set(plan.get("forbiddenNamespaces", []))
    if not FORBIDDEN <= forbidden:
        bad(f"forbiddenNamespaces incomplete: {sorted(forbidden)}")
    else:
        ok("forbidden namespaces enumerated (default/kube-system/argocd/prod/...)")

    cp = plan.get("createPolicy", {})
    if cp.get("neverDefaultNamespace") is not True or cp.get("neverClusterScoped") is not True:
        bad("createPolicy must never use default namespace / cluster scope")
    else:
        ok("createPolicy: never default namespace, never cluster-scoped, safe-only")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("NONPROD_NAMESPACE_PLAN_VERIFY: FAIL")
        return 1
    print("NONPROD_NAMESPACE_PLAN_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
