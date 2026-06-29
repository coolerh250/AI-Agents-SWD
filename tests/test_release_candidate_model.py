"""Step 60 -- release candidate builder."""

from __future__ import annotations

import pytest

from shared.sdk.release_governance import CandidateError, build_candidate


def test_candidate_defaults_nonprod() -> None:
    c = build_candidate(project_id=None, version_label="v1")
    assert c.target_environment == "nonprod"
    assert c.production_ready is False
    assert c.status == "draft"
    assert c.to_dict()["production_ready"] is False


def test_candidate_accepts_allowed_env() -> None:
    for env in ("dev", "test", "nonprod"):
        assert build_candidate(project_id=None, version_label="v", target_environment=env)


def test_candidate_rejects_production() -> None:
    for env in ("production", "prod"):
        with pytest.raises(CandidateError) as e:
            build_candidate(project_id=None, version_label="v", target_environment=env)
        assert e.value.reason == "production_environment_forbidden"
