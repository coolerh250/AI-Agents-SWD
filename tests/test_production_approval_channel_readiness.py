"""Step 63A -- production approval channel readiness."""

from __future__ import annotations

from shared.sdk.controlled_rollout import loaders


def test_no_send_no_approval() -> None:
    a = loaders.load("approval_channel")
    assert a.get("sends_external_notification") is False
    assert a.get("approval_granted") is False


def test_approval_items_missing() -> None:
    assert len(loaders.missing_approval_items()) == 4
