#!/usr/bin/env python3
"""Step 57 -- work-item lifecycle verifier."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.work_items import lifecycle  # noqa: E402

MARKER = "WORK_ITEM_LIFECYCLE_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    required = {
        "created",
        "triaged",
        "ready_for_dispatch",
        "dispatched",
        "in_progress",
        "waiting_approval",
        "blocked",
        "completed",
        "cancelled",
        "failed",
        "archived",
    }
    if not required <= set(lifecycle.states()):
        bad(f"missing states: {sorted(required - set(lifecycle.states()))}")
    # legal + illegal transitions
    if not lifecycle.can_transition("created", "triaged"):
        bad("created -> triaged must be allowed")
    if lifecycle.can_transition("created", "dispatched"):
        bad("created -> dispatched must NOT be allowed")
    if not lifecycle.can_transition("in_progress", "completed"):
        bad("in_progress -> completed must be allowed")
    if lifecycle.can_transition("completed", "in_progress"):
        bad("completed must be terminal (no re-dispatch)")
    if not lifecycle.can_transition("failed", "ready_for_dispatch"):
        bad("failed -> ready_for_dispatch (manual re-dispatch) must be allowed")
    # production_effect routing
    if lifecycle.next_state_for_dispatch(production_effect=True) != "waiting_approval":
        bad("production_effect must route to waiting_approval, never dispatched")
    if lifecycle.next_state_for_dispatch(production_effect=False) != "dispatched":
        bad("non-production work item should dispatch")
    if not lifecycle.is_terminal("completed"):
        bad("completed must be terminal")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] lifecycle states + transitions valid; production_effect -> waiting_approval")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
