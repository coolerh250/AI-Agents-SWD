#!/usr/bin/env python3
"""Step 54.4 -- security evidence package verifier.

Generates the evidence package (redacted) and asserts it is honest and
non-production: missing evidence is never marked clean, no secret / token / raw
finding evidence leaks, productionReady is false.

Marker: SECURITY_EVIDENCE_PACKAGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_security_evidence_package import build_evidence_package  # noqa: E402

SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.)"
)
REQUIRED_EVIDENCE = {
    "sast",
    "dependencyScan",
    "secretScan",
    "sbom",
    "imagePolicy",
    "dockerfileSecurity",
    "threatModel",
    "releaseRisk",
    "audit",
    "qa",
}
CLEAN_WORDS = {"clean", "passed", "ok", "ready"}

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    pkg = build_evidence_package()
    out = ROOT / ".runtime" / "security" / "security-evidence-package.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pkg, indent=2, sort_keys=True), encoding="utf-8")

    if pkg.get("productionReady") is not False:
        bad("evidence package productionReady must be false")
    else:
        ok("productionReady=false")

    evidence = pkg.get("evidence", {})
    missing_keys = REQUIRED_EVIDENCE - set(evidence)
    if missing_keys:
        bad(f"evidence package missing sections: {sorted(missing_keys)}")
    else:
        ok(f"all {len(REQUIRED_EVIDENCE)} evidence sections present")

    # Missing evidence must never be marked clean/present.
    for key, entry in evidence.items():
        status = str(entry.get("status", "")).lower()
        if status == "present":
            continue
        if status in CLEAN_WORDS or status not in (
            "not_run",
            "missing_evidence",
            "tool_unavailable",
        ):
            bad(f"evidence[{key}].status not honest: {status!r}")
    if not [f for f in failures if "not honest" in f]:
        ok("absent evidence recorded as not_run/missing_evidence (never clean)")

    blob = json.dumps(pkg)
    if SECRET_SHAPES.search(blob):
        bad("evidence package contains a secret-shaped value")
    else:
        ok("no secret / token shapes in evidence package")
    if "chain_of_thought" in blob or "reasoning_trace" in blob:
        bad("evidence package contains chain-of-thought")
    else:
        ok("no chain-of-thought")
    if "raw_finding" in blob or "raw_evidence" in blob:
        bad("evidence package contains raw finding evidence")
    else:
        ok("no raw finding evidence (references only)")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECURITY_EVIDENCE_PACKAGE_VERIFY: FAIL")
        return 1
    print("SECURITY_EVIDENCE_PACKAGE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
