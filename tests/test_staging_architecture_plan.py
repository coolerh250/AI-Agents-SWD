"""Step 64A -- staging architecture & deployment plan (planning docs, non-production only)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

DOCS = (
    "staging-architecture.md",
    "staging-deployment-plan.md",
    "staging-access-plan.md",
    "staging-scope-and-non-goals.md",
    "staging-service-inventory.md",
    "staging-admin-console-plan.md",
    "staging-demo-workflow-plan.md",
    "staging-information-request.md",
    "staging-risk-and-safety-plan.md",
    "staging-step64-roadmap.md",
)


@pytest.mark.parametrize("name", DOCS)
def test_staging_doc_exists(name: str) -> None:
    assert (STAGING / name).is_file(), name


@pytest.mark.parametrize("name", DOCS)
def test_staging_doc_is_non_production_only(name: str) -> None:
    text = (STAGING / name).read_text(encoding="utf-8")
    assert "staging-only=true" in text
    assert "non-production=true" in text
    assert "production-action=false" in text
    assert "production-ready=false" in text
    assert "production-ready=true" not in text
    assert "production-action=true" not in text


def test_service_inventory_includes_core_services() -> None:
    low = (STAGING / "staging-service-inventory.md").read_text(encoding="utf-8").lower()
    for svc in (
        "admin console",
        "orchestrator",
        "postgres",
        "redis",
        "policy-engine",
        "approval-engine",
        "audit-service",
    ):
        assert svc in low, svc


def test_information_request_includes_operator_questions() -> None:
    low = (STAGING / "staging-information-request.md").read_text(encoding="utf-8").lower()
    for need in (
        "10.0.1.32",
        "ssh username",
        "port",
        "auth",
        "demo",
        "sudo",
        "docker",
        "retention",
        "cleanup",
    ):
        assert need in low, need


def test_step64_roadmap_includes_64a_to_64g() -> None:
    text = (STAGING / "staging-step64-roadmap.md").read_text(encoding="utf-8")
    for stage in (
        "Step 64A",
        "Step 64B",
        "Step 64C",
        "Step 64D",
        "Step 64E",
        "Step 64F",
        "Step 64G",
    ):
        assert stage in text, stage


def test_no_production_action_allowed_anywhere() -> None:
    for name in DOCS:
        text = (STAGING / name).read_text(encoding="utf-8")
        for forbidden in (
            "production-deploy=true",
            "production-sync=true",
            "production-secret=true",
            "external-write=true",
            "github-merge=true",
            "image-push=true",
            "credential-storage=true",
        ):
            assert forbidden not in text, f"{name}:{forbidden}"
