#!/usr/bin/env python3
"""Step 60 -- promotion boundary model verifier (file-based).

Marker: PROMOTION_BOUNDARY_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "infra" / "release" / "promotion-boundary-model.yaml"
MARKER = "PROMOTION_BOUNDARY_MODEL_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}
    pb = data.get("promotionBoundary", {}) or {}
    transitions = pb.get("transitions") or []

    # the production transition must be explicitly not allowed
    prod_t = [t for t in transitions if t.get("to") == "production"]
    if not prod_t:
        bad("missing the operator_review->production transition definition")
    for t in prod_t:
        if t.get("allowed") is not False:
            bad("production transition must be allowed:false")
        if not t.get("requiresFutureProductionPhase"):
            bad("production transition must require a future production phase")

    # no auto transition anywhere
    for t in transitions:
        if t.get("auto") is True:
            bad(f"auto promotion not allowed: {t}")

    forbidden = pb.get("forbidden") or []
    for f in ("productionPromotion", "autoPromotion"):
        if f not in forbidden:
            bad(f"missing forbidden: {f}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] promotion boundary: production forbidden, no auto-promotion, future phase only")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
