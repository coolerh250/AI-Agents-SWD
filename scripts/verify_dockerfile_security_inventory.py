#!/usr/bin/env python3
"""Step 54.3 -- Dockerfile security inventory verifier.

Marker: DOCKERFILE_SECURITY_INVENTORY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess  # nosec: fixed argv, no shell
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "dockerfile-security-inventory.yaml"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not F.is_file():
        bad(f"missing {F}")
        print("DOCKERFILE_SECURITY_INVENTORY_VERIFY: FAIL")
        return 1
    dfs = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("dockerfiles", [])
    if not dfs:
        bad("no Dockerfiles inventoried")
        print("DOCKERFILE_SECURITY_INVENTORY_VERIFY: FAIL")
        return 1

    # cross-check count against the actual repo
    actual = sorted(
        f
        for f in subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
        ).stdout.split()
        if f.endswith("Dockerfile")
    )
    if len(dfs) != len(actual):
        bad(f"inventory covers {len(dfs)} Dockerfiles but repo has {len(actual)}")
    else:
        ok(f"all {len(actual)} Dockerfiles covered")

    for d in dfs:
        for field in ("hasUserInstruction", "runsAsRootByDefault", "baseImage", "exposesPorts"):
            if field not in d:
                bad(f"{d.get('path')} missing field {field}")
    if not [f for f in failures if "missing field" in f]:
        ok("USER / root / base image / ports recorded per Dockerfile")

    root_gaps = [d for d in dfs if d.get("runsAsRootByDefault")]
    if not root_gaps:
        bad("no root gaps recorded (expected: all 20 run as root)")
    else:
        ok(f"root gaps recorded ({len(root_gaps)} Dockerfiles run as root)")

    # honesty: a Dockerfile without USER must not be marked non-root
    for d in dfs:
        if not d.get("hasUserInstruction") and not d.get("runsAsRootByDefault"):
            bad(f"{d.get('path')} has no USER but is not marked root")
    if not [f for f in failures if "not marked root" in f]:
        ok("non-root readiness not falsely claimed")

    # secret-copy patterns checked field present
    if any("copiesSecrets" not in d for d in dfs):
        bad("copiesSecrets not assessed for every Dockerfile")
    elif any(d.get("copiesSecrets") for d in dfs):
        bad("a Dockerfile copies secrets")
    else:
        ok("no secret-copy pattern in any Dockerfile")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("DOCKERFILE_SECURITY_INVENTORY_VERIFY: FAIL")
        return 1
    print("DOCKERFILE_SECURITY_INVENTORY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
