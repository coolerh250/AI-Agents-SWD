#!/usr/bin/env python3
"""Step 54.2 -- scanner execution boundary verifier.

Marker: SCANNER_EXECUTION_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scanner-execution-boundary.yaml"

MUST_BE_FALSE = [
    "externalUploadAllowed",
    "networkAllowed",
    "tokenAllowed",
    "credentialAllowed",
    "githubWriteAllowed",
    "prCreationAllowed",
    "imagePushAllowed",
    "userProvidedPathAllowed",
    "productionGateMutationAllowed",
    "reportContainsSecretValues",
    "runtimeReportsCommitted",
]

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
        print("SCANNER_EXECUTION_BOUNDARY_VERIFY: FAIL")
        return 1
    b = (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("scannerExecution", {})
    if not b:
        bad("scannerExecution section missing")
        print("SCANNER_EXECUTION_BOUNDARY_VERIFY: FAIL")
        return 1

    if b.get("localOnly") is not True:
        bad("localOnly must be true")
    else:
        ok("scanner execution is local-only")

    for k in MUST_BE_FALSE:
        if b.get(k) is not False:
            bad(f"{k} must be false (got {b.get(k)!r})")
    if not [f for f in failures if "must be false" in f]:
        ok("no upload/network/token/credential/github/pr/image/path/gate; reports not committed")

    if not b.get("allowlistedTargetsOnly"):
        bad("allowlistedTargetsOnly must be true")
    if not b.get("allowedTargets"):
        bad("allowedTargets must be defined")
    if not [f for f in failures if "allowlist" in f or "allowedTargets" in f]:
        ok("allowlisted targets only")

    if not b.get("reportRedacted") or not b.get("nonProductionReportOnly"):
        bad("reports must be redacted and non-production only")
    else:
        ok("reports redacted; non-production only")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SCANNER_EXECUTION_BOUNDARY_VERIFY: FAIL")
        return 1
    print("SCANNER_EXECUTION_BOUNDARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
