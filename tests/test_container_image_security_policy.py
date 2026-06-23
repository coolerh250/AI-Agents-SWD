"""Step 54.1 -- container image security policy model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-image-security-policy.yaml"


def _c() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["containerImageSecurity"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _c()


def test_requirements_defined() -> None:
    r = _c()["requirements"]
    assert r["digestPinningRequired"] is True
    assert r["nonRootUserRequired"] is True
    assert r["imageVulnerabilityScanRequired"] is True
    assert r["imagePushInThisStage"] is False


def test_current_gaps_recorded() -> None:
    gaps = {g["key"] for g in _c()["currentGaps"]}
    assert "dockerfiles_missing_nonroot_user" in gaps
    assert "helm_images_not_digest_pinned" in gaps


def test_step51_observations_tracked() -> None:
    obs = _c()["step51Observations"]
    assert "job_image_pg_dump_psql_runtime_smoke_required" in obs
    assert _c()["productionReady"] is False
