#!/usr/bin/env python3
"""Step 62 -- production readiness runtime verifier.

Verifies the generated readiness gate report (when present) is well-formed and SAFE: not
production ready / approved / action-allowed, production_executed count 0, decision never
production_ready, no secret. The report lives under .runtime/ and is never committed.

Marker: PRODUCTION_READINESS_RUNTIME_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".runtime" / "readiness" / "production-readiness-gate-report.json"

MARKER = "PRODUCTION_READINESS_RUNTIME_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not REPORT.is_file():
        bad(
            f"missing readiness gate report: {REPORT.relative_to(ROOT).as_posix()} (run the generator)"
        )
        print(f"{MARKER}: FAIL")
        return 1
    d = json.loads(REPORT.read_text(encoding="utf-8"))
    if d.get("production_ready") is not False:
        bad("report production_ready must be false")
    if d.get("production_approval") is not False:
        bad("report production_approval must be false")
    if d.get("production_action_allowed") is not False:
        bad("report production_action_allowed must be false")
    if int(d.get("production_executed_true_count", 0) or 0) != 0:
        bad("report production_executed_true_count must be 0")
    dec = d.get("decision", {}).get("decision")
    if dec == "production_ready" or d.get("decision", {}).get("production_ready"):
        bad("decision must never be production_ready")
    if dec not in (
        "not_ready",
        "blocked_by_missing_evidence",
        "blocked_by_policy",
        "blocked_by_production_prerequisites",
        "ready_for_operator_review",
        "operator_review_requested",
    ):
        bad(f"invalid decision in report: {dec}")
    # No secret-shaped content.
    raw = json.dumps(d)
    for shape in ("ghp_", "-----BEGIN", "AKIA"):
        if shape in raw:
            bad(f"report contains secret-shaped content: {shape}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] readiness report: decision={dec}; not ready/approved; prod_exec=0; no secret")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
