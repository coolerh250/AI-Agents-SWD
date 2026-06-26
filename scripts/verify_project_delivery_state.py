#!/usr/bin/env python3
"""Step 57 -- project delivery-state rollup verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.projects import compute_delivery_state  # noqa: E402

MARKER = "PROJECT_DELIVERY_STATE_VERIFY"
MODEL = ROOT / "infra" / "delivery" / "project-delivery-state-model.yaml"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def wi(state: str, work_type: str = "task") -> dict:
    return {"lifecycle_state": state, "work_type": work_type}


def main() -> int:
    model = (yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}).get(
        "projectDeliveryStateModel", {}
    )
    if model.get("productionReady") is not False:
        bad("model productionReady must be false")
    states = set(model.get("states", []))
    if "completed_nonproduction" not in states or "operator_review" not in states:
        bad("model missing required delivery states")

    # rollup behaviour
    if compute_delivery_state([]) != "not_started":
        bad("no work items -> not_started")
    if compute_delivery_state([wi("blocked")]) != "blocked":
        bad("any blocked -> blocked")
    if compute_delivery_state([wi("waiting_approval")]) != "operator_review":
        bad("any waiting_approval -> operator_review")
    if compute_delivery_state([wi("in_progress", "qa")]) != "qa_active":
        bad("qa in_progress -> qa_active")
    if compute_delivery_state([wi("in_progress", "implementation")]) != "implementation_active":
        bad("implementation in_progress -> implementation_active")
    if compute_delivery_state([wi("completed", "task")]) != "completed_nonproduction":
        bad("all terminal + completed -> completed_nonproduction")
    # blocked precedence over waiting_approval
    if compute_delivery_state([wi("blocked"), wi("waiting_approval")]) != "blocked":
        bad("blocked must take precedence")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] delivery-state rollup deterministic; productionReady false; no auto-release")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
