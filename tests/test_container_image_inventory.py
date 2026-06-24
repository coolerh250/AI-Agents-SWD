"""Step 54.3 -- container image inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-image-inventory.yaml"


def _images() -> list:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("images", [])


def test_covers_compose_helm_job() -> None:
    sources = {s for img in _images() for s in (img.get("usedIn") or [])}
    assert {"compose", "helm", "job"} <= sources


def test_first_and_third_party_classified() -> None:
    imgs = _images()
    assert any(i["firstParty"] for i in imgs)
    assert any(not i["firstParty"] for i in imgs)


def test_no_image_falsely_digest_pinned() -> None:
    for i in _images():
        assert not (i.get("digestPinned") and not i.get("digest"))


def test_digest_gaps_and_no_latest() -> None:
    imgs = _images()
    assert all(i["digestPinned"] is False for i in imgs)  # none resolved
    assert all(i["latestTag"] is False for i in imgs)
    assert any(i.get("blockers") for i in imgs)


def test_batch_job_pg_client_blocker() -> None:
    batch = next(i for i in _images() if i["key"] == "batch-jobs")
    assert any("pg_dump_psql" in b for b in batch["blockers"])
