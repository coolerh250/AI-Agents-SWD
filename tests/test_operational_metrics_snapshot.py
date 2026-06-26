"""Step 58 -- operational metrics snapshot generator + redaction guarantees."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from shared.sdk.operations_metrics import build_snapshot

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_operational_metrics_snapshot.py"
SECRET_SHAPES = re.compile(r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN)")


def test_generator_writes_runtime_path_not_committed() -> None:
    src = GENERATOR.read_text(encoding="utf-8")
    assert ".runtime/operations/operational-metrics-snapshot.json" in src.replace("\\", "/") or (
        ".runtime" in src and "operational-metrics-snapshot.json" in src
    )
    assert "production_ready" in src


def test_snapshot_has_no_secret_shape_and_blockers_explicit() -> None:
    snap = asyncio.run(build_snapshot(ROOT))
    assert SECRET_SHAPES.search(json.dumps(snap)) is None
    assert isinstance(snap["blockers"], list)
    for name, d in snap["domains"].items():
        if d.get("available") is False:
            assert d.get("reason"), name
