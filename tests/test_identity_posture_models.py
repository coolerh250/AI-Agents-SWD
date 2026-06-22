"""Step 52.4 -- identity posture status model."""

from __future__ import annotations

from shared.sdk.identity_posture import (
    POSTURE_STATUSES,
    STATUS_FAILED,
    STATUS_MODELED,
    STATUS_UNKNOWN,
)


def test_status_enum_has_no_production_ready_value() -> None:
    assert STATUS_MODELED == "modeled_fail_closed_not_enabled"
    assert set(POSTURE_STATUSES) == {STATUS_MODELED, STATUS_FAILED, STATUS_UNKNOWN}
    for s in POSTURE_STATUSES:
        assert "production_identity_ready" not in s
        assert "oidc_enabled" not in s


def test_safety_fields_shape() -> None:
    from shared.sdk.identity_posture import identity_posture_safety_fields

    fields = identity_posture_safety_fields(None)
    assert fields["identity_production_ready"] is False
    assert fields["identity_posture_status"] == STATUS_UNKNOWN
