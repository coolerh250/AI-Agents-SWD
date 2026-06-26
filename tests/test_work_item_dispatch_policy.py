"""Step 57 -- work-item dispatch policy + resolver."""

from __future__ import annotations

import pytest

from shared.sdk.work_items import dispatcher
from shared.sdk.work_items.dispatcher import DispatchError


def test_routing() -> None:
    assert dispatcher.resolve_target("requirement")[0] == "requirement-agent"
    assert dispatcher.resolve_target("implementation")[0] == "development-agent"
    assert dispatcher.resolve_target("qa")[0] == "qa-agent"


def test_forbidden_targets_declared() -> None:
    forb = dispatcher.forbidden_targets()
    assert {
        "github-write",
        "argocd-sync",
        "production-executor",
        "external-notification-send",
    } <= forb


def test_production_effect_refused() -> None:
    with pytest.raises(DispatchError):
        dispatcher.build_dispatch_event(
            project_id="p",
            project_key="K",
            work_item_id="w",
            work_item_key="WI",
            dispatch_key="D",
            work_type="implementation",
            correlation_id="c",
            production_effect=True,
        )


def test_unknown_type_refused() -> None:
    with pytest.raises(DispatchError):
        dispatcher.resolve_target("nope")


def test_event_has_no_external_side_effect() -> None:
    ev = dispatcher.build_dispatch_event(
        project_id="p",
        project_key="K",
        work_item_id="w",
        work_item_key="WI",
        dispatch_key="D",
        work_type="qa",
        correlation_id="c",
        production_effect=False,
    )
    assert ev["github_write"] is False
    assert ev["argocd_sync"] is False
    assert ev["external_notification_send"] is False
    assert ev["production_action"] is False
