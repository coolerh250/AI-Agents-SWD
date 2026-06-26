#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD Application verifier (static).

Asserts the committed Application manifest is a manual-sync, non-production app:
project aiagents-nonprod, destination aiagents-smoke-dev, NO `automated` block (no
auto-sync / prune / self-heal), a single explicit source repo + non-production smoke
values, and no production namespace / values / namespace creation.

Marker: NONPROD_ARGOCD_APPLICATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_APPLICATION_VERIFY"
MANIFEST = ROOT / "infra" / "gitops" / "nonproduction" / "aiagents-smoke-application.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not MANIFEST.is_file():
        bad("missing aiagents-smoke-application.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    app = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    spec = app.get("spec", {})

    if app.get("kind") != "Application":
        bad("manifest is not an Application")
    if app.get("metadata", {}).get("namespace") != "argocd-nonprod":
        bad("Application must live in argocd-nonprod")
    if spec.get("project") != "aiagents-nonprod":
        bad("Application project must be aiagents-nonprod")

    dest = spec.get("destination", {})
    if dest.get("namespace") != "aiagents-smoke-dev":
        bad("destination namespace must be aiagents-smoke-dev")

    sync = spec.get("syncPolicy", {}) or {}
    if sync.get("automated") not in (None, {}):
        bad("Application must NOT set syncPolicy.automated (manual sync only)")
    # CreateNamespace must not be true.
    if "CreateNamespace=true" in (sync.get("syncOptions") or []):
        bad("CreateNamespace=true is forbidden")

    src = spec.get("source", {})
    repo = str(src.get("repoURL", ""))
    if not repo or "*" in repo:
        bad("source repoURL must be a single explicit repo (no wildcard)")
    path = str(src.get("path", ""))
    if "charts/ai-agents-platform" not in path:
        bad("source path must be the committed non-production Helm chart")
    vfiles = (src.get("helm", {}) or {}).get("valueFiles", [])
    if not any("nonprod" in str(v) for v in vfiles):
        bad("Application must use non-production smoke values")

    blob = MANIFEST.read_text(encoding="utf-8")
    if "namespace: production" in blob or "namespace: prod\n" in blob:
        bad("manifest references a production namespace")
    if "values-prod" in blob or "prod-placeholder" in blob:
        bad("manifest references production values")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] Application: manual-sync only; aiagents-smoke-dev; non-production smoke values")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
