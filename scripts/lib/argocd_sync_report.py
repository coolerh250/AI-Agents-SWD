"""Step 56 -- shared reader for the non-production ArgoCD manual-sync report.

The report is produced by ``scripts/run_nonproduction_argocd_manual_sync_report.py``
against the live non-production ArgoCD Application and written to
``.runtime/gitops/nonproduction-argocd-manual-sync-report.json`` (gitignored, NEVER
committed). The verifiers read it so a PASS reflects the real manual sync -- an
absent report means the sync has not run (BLOCKED), never a faked PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / ".runtime" / "gitops" / "nonproduction-argocd-manual-sync-report.json"


def load_report() -> dict[str, Any] | None:
    if not REPORT.is_file():
        return None
    try:
        return json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
