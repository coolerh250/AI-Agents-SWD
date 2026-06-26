#!/usr/bin/env python3
"""Strategy Note Checkpoint -- tenant-isolated workspace & controlled connector note.

Verifies the strategy note is present and correctly framed (future direction, NOT a
roadmap change, NOT an implementation), that overstated claims appear only in negated
form, that no tenant/connector runtime code was added, and that no production behaviour
is introduced.

Marker: TENANT_WORKSPACE_STRATEGY_NOTE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "TENANT_WORKSPACE_STRATEGY_NOTE_VERIFY"
NOTE = (
    ROOT
    / "docs"
    / "strategy"
    / "tenant-isolated-ai-workspace-controlled-connector-framework-strategy-note.md"
)

# Phrases that MUST be present (the note's framing).
REQUIRED = [
    "tenant-ready, not tenant-enabled",
    "not scheduled into the current Roadmap",
    "Step 57 remains completed as a multi-project baseline, not multi-tenant",
    "Step 58 (Admin Console v2 Operational Metrics) and Step 59",
    "are unchanged",
    "does not claim complete isolation is implemented",
    "does not claim production-grade multi-tenancy is implemented",
    "does not claim a BYOR connector is implemented",
]

# Overstated claims that may appear ONLY in a negated ("does not claim ...") context.
NEGATED_ONLY = [
    "complete isolation is implemented",
    "production-grade multi-tenancy is implemented",
    "byor connector is implemented",
]

# Tenant/connector RUNTIME paths that must NOT exist (no runtime added by this task).
FORBIDDEN_PATHS = [
    "shared/sdk/tenant",
    "shared/sdk/tenants",
    "shared/sdk/connectors",
    "shared/sdk/connector_framework",
    "apps/orchestrator/src/tenant_api.py",
    "apps/orchestrator/src/tenant_middleware.py",
    "apps/orchestrator/src/connector_api.py",
    "apps/orchestrator/src/connector_runtime.py",
]

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _only_negated(text_lower: str, claim: str) -> bool:
    idx = 0
    while True:
        i = text_lower.find(claim, idx)
        if i == -1:
            return True
        window = text_lower[max(0, i - 25) : i]
        if "does not claim" not in window:
            return False
        idx = i + len(claim)


def main() -> int:
    if not NOTE.is_file():
        bad("strategy note missing")
        print(f"{MARKER}: FAIL")
        return 1
    text = NOTE.read_text(encoding="utf-8")
    low = text.lower()

    for phrase in REQUIRED:
        if phrase not in text:
            bad(f"required phrase missing: {phrase!r}")

    for claim in NEGATED_ONLY:
        if not _only_negated(low, claim):
            bad(f"overstated claim appears in a non-negated form: {claim!r}")

    if "production_executed=true" in low or "production_executed = true" in low:
        bad("note must not set production_executed=true")

    # No tenant/connector runtime code added.
    for rel in FORBIDDEN_PATHS:
        if (ROOT / rel).exists():
            bad(f"forbidden tenant/connector runtime path exists: {rel}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] strategy note present + correctly framed; no runtime; no roadmap change")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
