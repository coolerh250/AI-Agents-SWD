"""Step 60 -- rollback requirement validation."""

from __future__ import annotations

from shared.sdk.release_governance import validate_rollback
from shared.sdk.release_governance import rollback


def test_plan_required() -> None:
    assert rollback.plan_required() is True


def test_empty_plan_invalid() -> None:
    valid, missing = validate_rollback(None)
    assert valid is False
    assert set(missing) == {
        "rollback_owner",
        "rollback_trigger",
        "rollback_steps",
        "rollback_validation",
    }


def test_complete_plan_valid() -> None:
    valid, missing = validate_rollback(
        {
            "rollback_owner": "ops",
            "rollback_trigger": "errors",
            "rollback_steps": ["revert"],
            "rollback_validation": "smoke",
        }
    )
    assert valid is True
    assert missing == []
