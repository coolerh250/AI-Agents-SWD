"""Step 64B.2A -- staging host runtime preparation (docs, non-production only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-host-runtime-preparation-report.md"
NOTES = STAGING / "staging-docker-installation-notes.md"
AFTER = STAGING / "staging-runtime-bootstrap-prerequisites-after-prep.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, NOTES, AFTER)


def test_preparation_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_docker_and_compose_status_documented() -> None:
    low = REPORT.read_text(encoding="utf-8").lower()
    assert "docker version" in low
    assert "docker compose version" in low
    assert "active" in low and "enabled" in low


def test_target_host_documented() -> None:
    for p in DOCS:
        assert "10.0.1.32" in p.read_text(encoding="utf-8"), p.name


def test_staging_directory_documented() -> None:
    both = "".join(p.read_text(encoding="utf-8") for p in DOCS)
    assert "/data/ai-agents-staging" in both


def test_no_runtime_deployment_claimed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "runtime-deployment=false" in text
        assert "runtime-deployment=true" not in text
        assert "docker-compose-up=false" in text
        assert "docker-compose-up=true" not in text
        assert "no ai agents runtime" in text.lower() or "no runtime" in text.lower()


def test_no_production_action_allowed() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "production-ready=false" in text
        assert "production-action=true" not in text
        assert "production-ready=true" not in text


def test_no_credential_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_hello_world_validation_only() -> None:
    low = REPORT.read_text(encoding="utf-8").lower()
    assert "hello-world" in low
    assert "validation-only" in low or "validation only" in low


def test_step64b2a_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64B.2A" in text
    assert "STAGING_HOST_RUNTIME_PREPARATION_VERIFY" in text
