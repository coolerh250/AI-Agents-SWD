#!/usr/bin/env python3
"""Step 57 -- work-item dispatch policy verifier."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.work_items import dispatcher  # noqa: E402
from shared.sdk.work_items.dispatcher import DispatchError  # noqa: E402

MARKER = "WORK_ITEM_DISPATCH_POLICY_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    # known routing
    try:
        agent, _ = dispatcher.resolve_target("requirement")
        if agent != "requirement-agent":
            bad("requirement should route to requirement-agent")
        agent, _ = dispatcher.resolve_target("implementation")
        if agent != "development-agent":
            bad("implementation should route to development-agent")
    except DispatchError as e:
        bad(f"resolve failed: {e}")

    # forbidden targets must be declared
    forb = dispatcher.forbidden_targets()
    for t in ("github-write", "argocd-sync", "production-executor", "external-notification-send"):
        if t not in forb:
            bad(f"forbidden target not declared: {t}")

    # production_effect direct dispatch refused
    try:
        dispatcher.build_dispatch_event(
            project_id="p",
            project_key="K",
            work_item_id="w",
            work_item_key="WI",
            dispatch_key="D",
            work_type="implementation",
            correlation_id="c",
            production_effect=True,
        )
        bad("production_effect dispatch must be refused")
    except DispatchError:
        pass

    # unknown work type refused
    try:
        dispatcher.resolve_target("totally-unknown")
        bad("unknown work type must be refused")
    except DispatchError:
        pass

    # event payload carries required fields + no external side effect
    ev = dispatcher.build_dispatch_event(
        project_id="p",
        project_key="K",
        work_item_id="w",
        work_item_key="WI",
        dispatch_key="D",
        work_type="qa",
        correlation_id="c",
        production_effect=False,
    )
    for k in (
        "project_id",
        "work_item_id",
        "dispatch_key",
        "target_agent",
        "correlation_id",
        "production_effect",
    ):
        if k not in ev:
            bad(f"dispatch event missing field: {k}")
    if (
        ev["github_write"]
        or ev["argocd_sync"]
        or ev["external_notification_send"]
        or ev["production_action"]
    ):
        bad("dispatch event must have all external side effects false")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] dispatch routing + forbidden targets + no production/external side effects")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
