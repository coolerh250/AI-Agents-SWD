#!/usr/bin/env python3
"""Step 51.3 -- ArgoCD manifest verifier (source-level).

Validates the GitOps manifests under infra/gitops/argocd: required files exist
and parse, kinds + project name are consistent, Applications reference the right
repo/revision/chart/values, NO automated sync / prune / selfHeal / hooks /
finalizers / credentials / Secret, the Project denies cluster-scoped resources
and Secret with a minimal namespaced whitelist, destinations are placeholders,
and the app-of-apps excludes staging + production. No cluster, no argocd CLI.

Marker: ARGOCD_MANIFESTS_VERIFY: PASS | FAIL
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
REPO = "https://github.com/coolerh250/AI-Agents-SWD.git"
PROJECT = "ai-agents-platform"
CHART_PATH = "infra/kubernetes/charts/ai-agents-platform"

REQUIRED = [
    "argocd/project.yaml",
    "argocd/applications/dev.yaml",
    "argocd/applications/test.yaml",
    "argocd/applications/staging-placeholder.yaml",
    "argocd/applications/production-placeholder.yaml",
    "argocd/app-of-apps/non-production.yaml",
    "gitops-environments.yaml",
    "policies/argocd-project-policy.yaml",
    "policies/application-safety-policy.yaml",
    "policies/production-isolation-policy.yaml",
]
ALLOWED_NS_KINDS = {
    "Deployment",
    "Service",
    "ConfigMap",
    "ServiceAccount",
    "NetworkPolicy",
    "PersistentVolumeClaim",
    "Job",
    "CronJob",
}
APP_VALUES = {
    "ai-agents-platform-dev": "values-dev.yaml",
    "ai-agents-platform-test": "values-test.yaml",
    "ai-agents-platform-staging-placeholder": "values-staging-placeholder.yaml",
    "ai-agents-platform-production-placeholder": "values-prod-placeholder.yaml",
}
# A destination is a safe placeholder if it is the in-cluster API (marked
# placeholder in the catalog) or an obvious *.invalid host.
SAFE_DEST = re.compile(r"^https://kubernetes\.default\.svc$|^https://[a-z0-9.-]+\.invalid$")
CRED_PAT = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|ssh-rsa |xox[baprs]-|AKIA[0-9A-Z]{16}|"
    r"(password|token|bearer)\s*[:=]\s*\S)",
    re.IGNORECASE,
)

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


def check_no_sync(name: str, spec: dict) -> None:
    sp = spec.get("syncPolicy", {}) or {}
    if "automated" in sp:
        bad(f"{name}: syncPolicy.automated must be absent (no auto-sync)")
    if sp.get("automated", {}) and sp["automated"].get("prune"):
        bad(f"{name}: prune must not be enabled")
    if sp.get("automated", {}) and sp["automated"].get("selfHeal"):
        bad(f"{name}: selfHeal must not be enabled")
    for opt in sp.get("syncOptions", []) or []:
        if "CreateNamespace=true" in opt:
            bad(f"{name}: CreateNamespace must not be true")
        if "allowEmpty=true" in opt.lower().replace(" ", ""):
            bad(f"{name}: allowEmpty must not be true")


def main() -> int:
    # 1. required files exist + parse
    for rel in REQUIRED:
        p = GITOPS / rel
        if not p.is_file():
            bad(f"missing required file: {rel}")
        else:
            try:
                yaml.safe_load(p.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                bad(f"{rel} does not parse: {e}")
    if not failures:
        ok(f"all {len(REQUIRED)} required GitOps files exist and parse")

    # 2. Project
    proj = load("argocd/project.yaml")
    if proj.get("kind") != "AppProject":
        bad("project.yaml kind must be AppProject")
    if proj.get("metadata", {}).get("name") != PROJECT:
        bad("project name must be ai-agents-platform")
    pspec = proj.get("spec", {})
    if pspec.get("sourceRepos") != [REPO]:
        bad(f"project sourceRepos must be exactly [{REPO}]")
    if pspec.get("clusterResourceWhitelist") != []:
        bad("project clusterResourceWhitelist must be empty (no cluster-scoped resources)")
    ns_kinds = {e.get("kind") for e in pspec.get("namespaceResourceWhitelist", [])}
    if not ns_kinds <= ALLOWED_NS_KINDS:
        bad(
            f"project namespaceResourceWhitelist has unexpected kinds: {ns_kinds - ALLOWED_NS_KINDS}"
        )
    if "Secret" in ns_kinds:
        bad("project must not allow Secret")
    blk = {e.get("kind") for e in pspec.get("namespaceResourceBlacklist", [])}
    if "Secret" not in blk:
        bad("project should blacklist Secret")
    for dest in pspec.get("destinations", []):
        if not SAFE_DEST.match(str(dest.get("server", ""))):
            bad(f"project destination server not a safe placeholder: {dest.get('server')}")
        if "production" in str(dest.get("namespace", "")):
            bad("project destinations must not include a production namespace")
    if not failures:
        ok(
            "AppProject restricts source repo, denies cluster-scoped + Secret, minimal namespaced whitelist"
        )

    # 3. Applications
    apps = {}
    for rel in (
        "argocd/applications/dev.yaml",
        "argocd/applications/test.yaml",
        "argocd/applications/staging-placeholder.yaml",
        "argocd/applications/production-placeholder.yaml",
    ):
        a = load(rel)
        name = a.get("metadata", {}).get("name", rel)
        apps[name] = a
        if a.get("kind") != "Application":
            bad(f"{name}: kind must be Application")
        spec = a.get("spec", {})
        if spec.get("project") != PROJECT:
            bad(f"{name}: project must be {PROJECT}")
        src = spec.get("source", {})
        if src.get("repoURL") != REPO:
            bad(f"{name}: repoURL must be {REPO}")
        if src.get("targetRevision") in (None, "", "HEAD", "*"):
            bad(f"{name}: targetRevision must be a fixed ref (not HEAD/*)")
        if src.get("path") != CHART_PATH:
            bad(f"{name}: source path must be {CHART_PATH}")
        vfs = src.get("helm", {}).get("valueFiles", [])
        want = APP_VALUES.get(name)
        if want and vfs != [want]:
            bad(f"{name}: valueFiles must be [{want}], got {vfs}")
        if want and not (CHART / want).is_file():
            bad(f"{name}: values file {want} does not exist")
        if a.get("metadata", {}).get("finalizers"):
            bad(f"{name}: must not declare finalizers")
        check_no_sync(name, spec)
        if not SAFE_DEST.match(str(spec.get("destination", {}).get("server", ""))):
            bad(f"{name}: destination is not a safe placeholder")
    if not [f for f in failures if "ai-agents-platform-" in f]:
        ok("Applications reference the project/repo/chart/values correctly with no auto-sync")

    # 4. app-of-apps excludes staging + production
    aoa = load("argocd/app-of-apps/non-production.yaml")
    aoa_spec = aoa.get("spec", {})
    inc = str(aoa_spec.get("source", {}).get("directory", {}).get("include", ""))
    if "staging" in inc or "production" in inc:
        bad("app-of-apps include must not reference staging/production")
    if "dev.yaml" not in inc or "test.yaml" not in inc:
        bad("app-of-apps must include dev.yaml + test.yaml only")
    check_no_sync("app-of-apps", aoa_spec)
    if aoa.get("metadata", {}).get("finalizers"):
        bad("app-of-apps must not declare finalizers")
    if not [f for f in failures if "app-of-apps" in f]:
        ok("app-of-apps includes dev+test only (staging/production excluded), no auto-sync")

    # 5. no credentials / Secret / hooks anywhere in argocd manifests
    for p in ARGOCD.rglob("*.yaml"):
        raw = p.read_text(encoding="utf-8")
        if CRED_PAT.search(raw):
            bad(f"{p.name}: credential-like string present")
        for d in yaml.safe_load_all(raw):
            if isinstance(d, dict) and d.get("kind") == "Secret":
                bad(f"{p.name}: Secret resource forbidden")
        if "argocd.argoproj.io/hook" in raw or "helm.sh/hook" in raw:
            bad(f"{p.name}: sync hook annotation forbidden")
        if "argocd-image-updater" in raw or "notifications.argoproj.io" in raw:
            bad(f"{p.name}: image-updater/notifications annotation forbidden")
    if not [f for f in failures if "credential" in f or "Secret" in f or "hook" in f]:
        ok("no credentials, no Secret resource, no hooks/image-updater/notifications")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ARGOCD_MANIFESTS_VERIFY: FAIL")
        return 1
    print("ARGOCD_MANIFESTS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
