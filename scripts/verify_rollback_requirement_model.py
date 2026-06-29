#!/usr/bin/env python3
"""Step 60 -- rollback requirement model verifier (file + SDK).

Marker: ROLLBACK_REQUIREMENT_MODEL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / "infra" / "release" / "rollback-requirement-model.yaml"
MARKER = "ROLLBACK_REQUIREMENT_MODEL_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    data = yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}
    rb = data.get("rollbackRequirement", {}) or {}
    if rb.get("rollback_plan_required") is not True:
        bad("rollback_plan_required must be true")
    if rb.get("rollback_evidence_required") is not True:
        bad("rollback_evidence_required must be true")

    from shared.sdk.release_governance import validate_rollback

    valid_empty, missing = validate_rollback(None)
    if valid_empty is not False or not missing:
        bad("empty rollback plan must be invalid with missing fields")

    valid_full, _ = validate_rollback(
        {
            "rollback_owner": "ops",
            "rollback_trigger": "error rate",
            "rollback_steps": ["revert"],
            "rollback_validation": "smoke",
        }
    )
    if valid_full is not True:
        bad("complete rollback plan must be valid")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] rollback: plan required; empty invalid; complete valid; no rollback triggered")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
