"""Step 62 -- readiness evidence inventory."""

from __future__ import annotations

from shared.sdk.production_readiness import evidence


def test_no_production_scope() -> None:
    assert evidence.production_scope_count() == 0
    for e in evidence.load_evidence():
        assert e["production_scope"] is False
        assert e["nonproduction_only"] is True


def test_required_fields_present() -> None:
    fields = {
        "source",
        "freshness",
        "availability",
        "redaction",
        "production_scope",
        "nonproduction_only",
        "blocking_limitations",
    }
    items = evidence.load_evidence()
    assert items
    for e in items:
        assert fields <= set(e.keys())


def test_step_evidence_present() -> None:
    names = {e["name"] for e in evidence.load_evidence()}
    for n in (
        "step60_release_deployment_governance",
        "step61_backup_restore_dr_operations",
        "tenant_strategy_note",
    ):
        assert n in names
