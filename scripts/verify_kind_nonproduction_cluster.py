#!/usr/bin/env python3
"""Step 55.1 -- kind non-production cluster verifier.

Validates the committed kind cluster definition (always): local-only, no public
ingress / LoadBalancer / host port mapping, safe name. When kind + a cluster are
present it confirms the cluster exists with a safe (non-production) context.
Never prints a kubeconfig / token / context name. With no cluster it reports
BLOCKED.

Marker: KIND_NONPROD_CLUSTER_VERIFY: PASS | BLOCKED | FAIL
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KIND_NONPROD_CLUSTER_VERIFY"
CFG = ROOT / "infra" / "kubernetes" / "kind" / "nonproduction-kind-cluster.yaml"
CLUSTER = "aiagents-smoke"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not CFG.is_file():
        bad("missing nonproduction-kind-cluster.yaml")
        print(f"{MARKER}: FAIL")
        return 1
    raw = CFG.read_text(encoding="utf-8")
    cfg = yaml.safe_load(raw) or {}
    if cfg.get("name") != CLUSTER:
        bad(f"kind cluster name must be {CLUSTER}")
    if "prod" in str(cfg.get("name", "")).lower():
        bad("kind cluster name must not contain a production substring")
    # Local-only: forbid host port mappings / ingress-ready / LoadBalancer hints.
    if "extraPortMappings" in raw:
        bad("kind config must not expose host ports (no public ingress)")
    for forbidden in ("LoadBalancer", "ingress-ready"):
        if forbidden in raw:
            bad(f"kind config must not reference {forbidden}")
    if not failures:
        print("  [OK] kind config is local-only; no host ports / ingress / LoadBalancer")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    if shutil.which("kind") is None or shutil.which("kubectl") is None:
        print("  [BLOCKED] kind/kubectl not installed")
        print(f"{MARKER}: BLOCKED")
        return 0
    try:
        out = subprocess.run(  # noqa: S603
            ["kind", "get", "clusters"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        print("  [BLOCKED] kind not usable")
        print(f"{MARKER}: BLOCKED")
        return 0
    if CLUSTER not in out.stdout.split():
        print(f"  [BLOCKED] kind cluster '{CLUSTER}' not created yet")
        print(f"{MARKER}: BLOCKED")
        return 0
    try:
        ctx = subprocess.run(  # noqa: S603
            ["kubectl", "config", "current-context"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        print("  [BLOCKED] cannot read current context")
        print(f"{MARKER}: BLOCKED")
        return 0
    name = ctx.stdout.strip().lower()
    if "prod" in name or "production" in name:
        bad("current context looks production")
        print(f"{MARKER}: FAIL")
        return 1
    if not name.startswith("kind-"):
        print("  [BLOCKED] current context is not the kind cluster")
        print(f"{MARKER}: BLOCKED")
        return 0
    print(f"  [OK] kind cluster '{CLUSTER}' present with a safe non-production context")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
