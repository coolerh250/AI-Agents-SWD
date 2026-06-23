#!/usr/bin/env python3
"""Step 54.1 -- security scan policy baseline verifier.

Asserts the SAST / dependency / secret scan / SBOM / container image policies
exist and are modeled_not_enforced / configured=false with no production claim.

Marker: SECURITY_SCAN_POLICY_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "security"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _load(name: str) -> dict:
    p = SDIR / name
    if not p.is_file():
        bad(f"missing {name}")
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def main() -> int:
    catalog = _load("security-scan-policy-catalog.yaml")
    sast = _load("sast-policy-model.yaml").get("sast", {})
    depscan = _load("dependency-scan-policy-model.yaml").get("dependencyScan", {})
    secretscan = _load("secret-scan-policy-model.yaml").get("secretScan", {})
    sbom = _load("sbom-policy-model.yaml").get("sbom", {})
    image = _load("container-image-security-policy.yaml").get("containerImageSecurity", {})

    if not catalog.get("policies"):
        bad("scan policy catalog has no policies")
    else:
        ok(f"scan policy catalog present with {len(catalog['policies'])} policies")
    for pol in catalog.get("policies", []):
        if pol.get("status") != "modeled_not_enforced":
            bad(f"policy {pol.get('key')} status must be modeled_not_enforced")
    if catalog.get("productionEnforced") is not False:
        bad("catalog productionEnforced must be false")
    if not [f for f in failures if "modeled_not_enforced" in f or "productionEnforced" in f]:
        ok("all catalog policies modeled_not_enforced; productionEnforced=false")

    for name, model in (
        ("sast", sast),
        ("dependencyScan", depscan),
        ("secretScan", secretscan),
        ("sbom", sbom),
    ):
        if not model:
            bad(f"{name} policy missing")
            continue
        if model.get("configured") is not False:
            bad(f"{name}.configured must be false")
        if model.get("productionReady") is not False:
            bad(f"{name}.productionReady must be false")
    if not image:
        bad("container image policy missing")
    elif image.get("productionReady") is not False:
        bad("container image policy productionReady must be false")
    if not [
        f for f in failures if ".configured" in f or "productionReady" in f or "policy missing" in f
    ]:
        ok("SAST/dependency/secret/SBOM/container policies configured=false, productionReady=false")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_SCAN_POLICY_BASELINE_VERIFY: FAIL")
        return 1
    print("SECURITY_SCAN_POLICY_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
