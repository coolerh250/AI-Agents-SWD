"""Step 62 -- deployment authorization boundary."""

from __future__ import annotations

import pytest

from shared.sdk.production_readiness import authorization


@pytest.mark.parametrize(
    "forbidden",
    [
        "production_deploy",
        "production_sync",
        "production_restore",
        "production_failover",
        "pr_merge",
        "image_push",
        "release_creation",
        "tag_creation",
    ],
)
def test_may_not_authorize(forbidden: str) -> None:
    assert forbidden in authorization.may_not_authorize()
    assert forbidden not in authorization.may_authorize()


def test_operator_review_is_not_approval() -> None:
    assert authorization.operator_review_is_approval() is False


def test_may_authorize_is_review_only() -> None:
    may = set(authorization.may_authorize())
    assert may <= {
        "readiness_review_package",
        "operator_review_request",
        "production_rollout_planning",
    }
