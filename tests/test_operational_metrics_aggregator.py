"""Step 58 -- operational metrics aggregator (no DB required: degrades cleanly)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from shared.sdk.operations_metrics import build_snapshot
from shared.sdk.operations_metrics import collectors

ROOT = Path(__file__).resolve().parents[1]


def test_snapshot_structure_and_production_ready_false() -> None:
    snap = asyncio.run(build_snapshot(ROOT))
    assert snap["production_ready"] is False
    assert snap["status"] == "modeled_not_production_ready"
    for key in ("generated_at", "domains", "freshness", "limitations", "blockers"):
        assert key in snap
    # All 11 domains present (available or explicitly unavailable).
    assert {
        "delivery",
        "work_items",
        "dispatch",
        "agents",
        "workflows",
        "runtime",
        "gitops",
        "security",
        "approval",
        "audit",
        "safety",
    } <= set(snap["domains"])


def test_missing_runtime_report_is_unavailable_with_reason(tmp_path: Path) -> None:
    # A root with no .runtime report -> runtime collector unavailable, never clean.
    rt = collectors.collect_runtime(tmp_path)
    assert rt["available"] is False
    assert rt.get("reason")
