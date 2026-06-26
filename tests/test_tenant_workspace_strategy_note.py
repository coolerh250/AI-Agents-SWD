"""Strategy Note Checkpoint -- tenant-isolated workspace & connector strategy note."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = (
    ROOT
    / "docs"
    / "strategy"
    / "tenant-isolated-ai-workspace-controlled-connector-framework-strategy-note.md"
)

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


def test_note_exists_with_title() -> None:
    assert NOTE.is_file()
    text = NOTE.read_text(encoding="utf-8")
    assert (
        "Tenant-Isolated AI Workspace & Controlled Connector Framework — Strategy Note v1" in text
    )


def test_required_phrases_present() -> None:
    text = NOTE.read_text(encoding="utf-8")
    for phrase in (
        "tenant-ready, not tenant-enabled",
        "not scheduled into the current Roadmap",
        "Step 57 remains completed as a multi-project baseline, not multi-tenant",
        "are unchanged",
        "does not claim complete isolation is implemented",
        "does not claim production-grade multi-tenancy is implemented",
        "does not claim a BYOR connector is implemented",
    ):
        assert phrase in text, phrase


def test_overstated_claims_only_negated() -> None:
    low = NOTE.read_text(encoding="utf-8").lower()
    for claim in (
        "complete isolation is implemented",
        "production-grade multi-tenancy is implemented",
        "byor connector is implemented",
    ):
        idx = 0
        while True:
            i = low.find(claim, idx)
            if i == -1:
                break
            assert "does not claim" in low[max(0, i - 25) : i], claim
            idx = i + len(claim)


def test_no_production_execution_claim() -> None:
    low = NOTE.read_text(encoding="utf-8").lower()
    assert "production_executed=true" not in low
    assert "production_executed = true" not in low


def test_no_tenant_or_connector_runtime_added() -> None:
    for rel in FORBIDDEN_PATHS:
        assert not (ROOT / rel).exists(), rel


def test_roadmap_not_scheduled_for_tenant_work() -> None:
    text = NOTE.read_text(encoding="utf-8")
    assert (
        "introduces no new scheduled work" in text.lower()
        or "no new scheduled work" in text.lower()
    )
    # Step 58 / 59 referenced as unchanged, not rescheduled.
    assert "Step 58" in text and "Step 59" in text
