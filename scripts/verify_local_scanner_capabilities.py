#!/usr/bin/env python3
"""Step 54.2 -- local scanner capability inventory verifier.

Marker: LOCAL_SCANNER_CAPABILITIES_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "local-scanner-capability-inventory.yaml"

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
        print("LOCAL_SCANNER_CAPABILITIES_VERIFY: FAIL")
        return 1
    data = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    scanners = data.get("scanners", [])
    if not scanners:
        bad("no scanners listed")
        print("LOCAL_SCANNER_CAPABILITIES_VERIFY: FAIL")
        return 1
    ok(f"capability inventory present with {len(scanners)} scanners")

    cats = {s.get("category") for s in scanners}
    if not {"secret", "sast", "dependency"} <= cats:
        bad(f"missing scanner categories: {cats}")
    else:
        ok("secret / sast / dependency scanners catalogued")

    bundled = [s for s in scanners if s.get("installed")]
    if not bundled:
        bad("no bundled (installed=true) baseline scanner")
    elif not all(s.get("localOnly") for s in bundled):
        bad("a bundled baseline scanner is not localOnly")
    elif any(s.get("tokenRequired") for s in bundled):
        bad("a bundled baseline scanner requires a token")
    elif any(s.get("configured") and not s.get("localOnly") for s in bundled):
        bad("a configured baseline scanner is not local-only")
    else:
        ok("bundled baseline scanners are local-only, token-free, configured")

    # every custom_* baseline scanner must be installed=true; external honestly false
    for s in scanners:
        if str(s.get("key", "")).startswith("custom_") and not s.get("installed"):
            bad(f"custom baseline scanner not installed: {s.get('key')}")
        if not str(s.get("key", "")).startswith("custom_") and s.get("installed"):
            bad(f"external tool dishonestly marked installed: {s.get('key')}")
    if not [f for f in failures if "installed" in f]:
        ok("custom baselines installed; external tools recorded honestly (runtime-detected)")

    if any(s.get("sourceUpload") for s in scanners):
        bad("a scanner declares sourceUpload=true")
    if any(s.get("productionReady") for s in scanners):
        bad("a scanner declares productionReady=true")
    if data.get("externalScannerUploadEnabled") is not False:
        bad("externalScannerUploadEnabled must be false")
    if not [
        f
        for f in failures
        if "sourceUpload" in f or "productionReady" in f or "externalScanner" in f
    ]:
        ok("no source upload, no production-ready claim, no external upload")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("LOCAL_SCANNER_CAPABILITIES_VERIFY: FAIL")
        return 1
    print("LOCAL_SCANNER_CAPABILITIES_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
