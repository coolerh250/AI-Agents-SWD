"""Step 55.1 -- shared reader for the non-production runtime smoke report.

The report is produced by ``scripts/run_nonproduction_runtime_smoke.py`` against a
live safe non-production cluster and written to
``.runtime/kubernetes/nonproduction-runtime-smoke-report.json`` (gitignored, NEVER
committed). The section verifiers read it so a PASS reflects the real cluster
smoke -- absent report means the smoke has not run (BLOCKED), never a faked PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / ".runtime" / "kubernetes" / "nonproduction-runtime-smoke-report.json"


def load_report() -> dict[str, Any] | None:
    if not REPORT.is_file():
        return None
    try:
        return json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def section_status(name: str) -> str | None:
    """Return the report section status ('pass'/'fail'), or None if no report."""
    report = load_report()
    if report is None:
        return None
    return ((report.get("sections") or {}).get(name) or {}).get("status")
