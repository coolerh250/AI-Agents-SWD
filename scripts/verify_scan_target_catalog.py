#!/usr/bin/env python3
"""Step 54.2 -- scan target catalog verifier.

Marker: SCAN_TARGET_CATALOG_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scan-target-catalog.yaml"
EXC = ROOT / "infra" / "security" / "scan-exclusion-policy.yaml"

MUST_EXCLUDE = {".git", ".venv", "node_modules"}
MUST_NOT_EXCLUDE_TOP = {"apps", "agents", "shared", "infra"}

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
        print("SCAN_TARGET_CATALOG_VERIFY: FAIL")
        return 1
    t = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("targets", {})
    secret = t.get("secretScan", {})
    sast = t.get("sast", {})
    dep = t.get("dependencyScan", {})

    if not secret.get("include") or not sast.get("include"):
        bad("secretScan/sast include not defined")
    else:
        ok("include defined for secret + sast scans")

    sec_exc = set(secret.get("exclude", []))
    if not MUST_EXCLUDE <= sec_exc:
        bad(f"secret scan must exclude {MUST_EXCLUDE}, got {sec_exc}")
    else:
        ok(".git/.venv/node_modules excluded from secret scan")

    # production code top-level dirs must not be excluded
    if MUST_NOT_EXCLUDE_TOP & sec_exc:
        bad(f"production code dirs excluded from secret scan: {MUST_NOT_EXCLUDE_TOP & sec_exc}")
    else:
        ok("production code dirs not hidden")

    pkg = set(dep.get("packageFiles", []))
    for needed in ("requirements.txt", "package.json", "package-lock.json"):
        if needed not in pkg:
            bad(f"dependency scan missing package file: {needed}")
    if not [f for f in failures if "package file" in f]:
        ok("package files not excluded (requirements / package / lock present)")

    # exclusion policy must forbid hiding Dockerfiles / package files / manifests
    if EXC.is_file():
        pol = (yaml.safe_load(EXC.read_text(encoding="utf-8")) or {}).get("exclusionPolicy", {})
        mnh = set(pol.get("mustNotHide", []))
        if not {"dockerfiles", "requirements_or_package_files", "helm_or_gitops_manifests"} <= mnh:
            bad("exclusion policy does not forbid hiding dockerfiles/package/manifests")
        else:
            ok("exclusion policy forbids hiding dockerfiles/package files/manifests")
    else:
        bad("scan-exclusion-policy.yaml missing")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SCAN_TARGET_CATALOG_VERIFY: FAIL")
        return 1
    print("SCAN_TARGET_CATALOG_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
