#!/usr/bin/env python3
"""Step 51.3 -- GitOps production isolation verifier (source-level).

Asserts the production placeholder Application is disabled, do-not-sync, never in
any app-of-apps, points at an obvious placeholder destination, carries no
credentials, and that the production values stay fail-closed (no deploy, PVC,
batch render, operator actions, backup schedule, external egress, secret). No
cluster, no argocd CLI.

Marker: GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITOPS = ROOT / "infra" / "gitops"
ARGOCD = GITOPS / "argocd"
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
PROD_APP = "ai-agents-platform-production-placeholder"
STAGING_APP = "ai-agents-platform-staging-placeholder"
CRED_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|ssh-rsa |xox[baprs]-|AKIA[0-9A-Z]{16}|"
    r"(password|token|bearer)\s*[:=]\s*\S)",
    re.IGNORECASE,
)
REQUIRED_PROD_ANNOTATIONS = [
    "ai-agents-swd/disabled-placeholder",
    "ai-agents-swd/do-not-sync",
    "ai-agents-swd/production-placeholder",
    "ai-agents-swd/real-deploy-enabled",
    "ai-agents-swd/requires-operator-approval",
    "ai-agents-swd/requires-production-oidc",
    "ai-agents-swd/requires-secret-store",
    "ai-agents-swd/requires-image-digest",
    "ai-agents-swd/requires-backup-target",
    "ai-agents-swd/requires-runtime-smoke",
]

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def load(rel: str) -> dict:
    return yaml.safe_load((GITOPS / rel).read_text(encoding="utf-8"))


def main() -> int:
    prod = load("argocd/applications/production-placeholder.yaml")
    ann = prod.get("metadata", {}).get("annotations", {}) or {}

    # 1. required disabled/isolation annotations
    for a in REQUIRED_PROD_ANNOTATIONS:
        if a not in ann:
            bad(f"production placeholder missing annotation {a}")
    if str(ann.get("ai-agents-swd/real-deploy-enabled", "")).lower() != "false":
        bad("production real-deploy-enabled must be false")
    if not failures:
        ok("production placeholder carries all disabled/isolation annotations")

    # 2. no automated sync
    sp = prod.get("spec", {}).get("syncPolicy", {}) or {}
    if "automated" in sp:
        bad("production placeholder must not have automated sync")
    else:
        ok("production placeholder has no automated sync")

    # 3. obvious placeholder destination (.invalid), placeholder namespace
    dest = prod.get("spec", {}).get("destination", {})
    if not str(dest.get("server", "")).endswith(".invalid"):
        bad(
            f"production destination must be an obvious .invalid placeholder (got {dest.get('server')})"
        )
    if "placeholder" not in str(dest.get("namespace", "")):
        bad("production namespace must be a placeholder")
    if not [f for f in failures if "destination" in f or "namespace" in f]:
        ok("production destination + namespace are obvious placeholders")

    # 4. excluded from app-of-apps
    aoa = (ARGOCD / "app-of-apps" / "non-production.yaml").read_text(encoding="utf-8")
    inc = str(yaml.safe_load(aoa)["spec"]["source"].get("directory", {}).get("include", ""))
    if "production" in inc or "staging" in inc:
        bad("app-of-apps must exclude staging + production")
    else:
        ok("production + staging excluded from app-of-apps")

    # 5. project allows no production namespace
    proj = load("argocd/project.yaml")
    for d in proj.get("spec", {}).get("destinations", []):
        if "production" in str(d.get("namespace", "")) or d.get("namespace") == "*":
            bad("project must not allow a production/wildcard namespace")
    if not [f for f in failures if "project must not" in f]:
        ok("project destinations exclude production/wildcard namespaces")

    # 6. no credentials anywhere in argocd manifests
    for p in ARGOCD.rglob("*.yaml"):
        if CRED_PAT.search(p.read_text(encoding="utf-8")):
            bad(f"{p.name}: credential-like string present")
    if not [f for f in failures if "credential" in f]:
        ok("no credential-like strings in GitOps manifests")

    # 7. production values fail closed
    base = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    over = yaml.safe_load((CHART / "values-prod-placeholder.yaml").read_text(encoding="utf-8"))

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out

    pv = merge(base, over)
    checks = {
        "realDeployEnabled": pv["global"]["realDeployEnabled"] is False,
        "operatorActions": pv["platform"]["adminConsole"]["operatorActionsEnabled"] is False,
        "productionBackupSchedule": pv["platform"]["integrations"]["productionBackupSchedule"]
        is False,
        "noInternalPostgres": pv["components"]["postgres"]["enabled"] is False,
        "noInternalRedis": pv["components"]["redis"]["enabled"] is False,
        "externalEgressOff": pv["networkPolicy"]["externalEgress"]["enabled"] is False,
        "noMigrationJob": pv["batchJobs"]["migration"]["renderTemplate"] is False,
        "noBackupJob": pv["batchJobs"]["backup"]["renderTemplate"] is False,
        "noRestoreJob": pv["batchJobs"]["restore"]["renderTemplate"] is False,
        "noGeneratedPVC": pv["storage"]["postgres"]["strategy"] != "generatedPVC"
        and pv["storage"]["redis"]["strategy"] != "generatedPVC",
    }
    for k, good in checks.items():
        if not good:
            bad(f"production values not fail-closed: {k}")
    if not [f for f in failures if "fail-closed" in f]:
        ok("production values fail closed (deploy/PVC/batch/egress/operator/backup all off)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("GITOPS_PRODUCTION_ISOLATION_VERIFY: FAIL")
        return 1
    print("GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
