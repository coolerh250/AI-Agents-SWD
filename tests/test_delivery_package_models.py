"""Stage 49 -- delivery package model validation + defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.delivery_package.models import (
    REQUIRED_SECTION_KEYS,
    DeliveryPackage,
    DeliveryPackageRequest,
    DeliveryPackageResult,
)


def test_package_controlled_only_defaults() -> None:
    pkg = DeliveryPackage(package_key="pkg-1")
    assert pkg.controlled_only is True
    assert pkg.human_acceptance_required is True
    assert pkg.human_acceptance_status == "pending"
    assert pkg.real_llm_enabled is False
    assert pkg.github_write_enabled is False
    assert pkg.pr_creation_enabled is False
    assert pkg.deployment_enabled is False
    assert pkg.external_delivery_enabled is False
    assert pkg.production_executed is False


def test_result_safe_defaults() -> None:
    res = DeliveryPackageResult()
    assert res.production_executed is False
    assert res.pr_created is False
    assert res.deployment_performed is False
    assert res.real_llm_used is False
    assert res.external_delivery_performed is False
    assert res.human_acceptance_status == "pending"


def test_request_requires_pilot_id() -> None:
    with pytest.raises(ValidationError):
        DeliveryPackageRequest()


def test_strict_models_forbid_extra() -> None:
    with pytest.raises(ValidationError):
        DeliveryPackage(package_key="pkg-1", bogus_field=True)


def test_required_sections_count() -> None:
    assert len(REQUIRED_SECTION_KEYS) == 14
