#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD project policy verifier (static).

Asserts the committed AppProject manifest matches the restricted policy descriptor:
single non-production destination (aiagents-smoke-dev), no wildcard destination, no
cluster-scoped resources, a single explicit source repo (no wildcard), and only the
allowed namespaced kinds.

Marker: NONPROD_ARGOCD_PROJECT_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_PROJECT_POLICY_VERIFY"
POLICY = ROOT / "infra" / "gitops" / "nonproduction-argocd-project-policy.yaml"
MANIFEST = ROOT / "infra" / "gitops" / "nonproduction" / "aiagents-nonprod-project.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for f in (POLICY, MANIFEST):
        if not f.is_file():
            bad(f"missing {f.name}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    pol = (
        (yaml.safe_load(POLICY.read_text(encoding="utf-8")) or {})
        .get("nonProductionArgocdProjectPolicy", {})
        .get("project", {})
    )
    proj = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    spec = proj.get("spec", {})

    if proj.get("kind") != "AppProject":
        bad("manifest is not an AppProject")
    if proj.get("metadata", {}).get("name") != "aiagents-nonprod":
        bad("AppProject name must be aiagents-nonprod")
    if proj.get("metadata", {}).get("namespace") != "argocd-nonprod":
        bad("AppProject must live in argocd-nonprod")

    dests = spec.get("destinations", [])
    if len(dests) != 1 or dests[0].get("namespace") != "aiagents-smoke-dev":
        bad("project destination must be exactly aiagents-smoke-dev")
    for d in dests:
        if "*" in str(d.get("namespace", "")) or "*" in str(d.get("server", "")):
            bad("wildcard destination is forbidden")

    repos = spec.get("sourceRepos", [])
    if not repos or any(r == "*" for r in repos):
        bad("sourceRepos must be a single explicit repo (no wildcard)")

    if spec.get("clusterResourceWhitelist") not in ([], None):
        bad("clusterResourceWhitelist must be empty (no cluster-scoped resources)")

    allowed = {(w.get("kind")) for w in spec.get("namespaceResourceWhitelist", [])}
    required = set(pol.get("namespaceResourceWhitelist", {}).get("allowed", []))
    if not required <= allowed:
        bad(f"namespaceResourceWhitelist missing kinds: {sorted(required - allowed)}")
    # No production / default namespace destination.
    blob = MANIFEST.read_text(encoding="utf-8")
    if "namespace: production" in blob or "namespace: default" in blob:
        bad("manifest references a production/default namespace")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        "  [OK] AppProject restricted: single non-prod destination, no wildcard, no cluster scope"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
