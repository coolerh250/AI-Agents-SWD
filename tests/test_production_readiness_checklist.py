"""Step 62 -- production readiness checklist."""

from __future__ import annotations

from shared.sdk.production_readiness import checklist


def test_categories_present() -> None:
    cats = checklist.load_categories()
    assert len(cats) == 17
    names = {c["name"] for c in cats}
    for required in (
        "identity",
        "secret_management",
        "release_governance",
        "backup_restore_dr",
        "operator_review",
    ):
        assert required in names


def test_no_production_ready_claim_allowed() -> None:
    assert checklist.production_ready_claim_count() == 0
    for c in checklist.load_categories():
        assert c["production_ready_claim_allowed"] is False


def test_required_fields_present() -> None:
    fields = {
        "required",
        "evidence_source",
        "status",
        "blocking_if_missing",
        "production_ready_claim_allowed",
    }
    for c in checklist.load_categories():
        assert fields <= set(c.keys())
