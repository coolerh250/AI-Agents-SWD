"""Stage 48 -- mini delivery pilot Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.mini_delivery_pilot.models import (
    MiniDeliveryPilot,
    MiniDeliveryPilotRequest,
    MiniDeliveryPilotResult,
    SafetyEvidenceReport,
)


def test_pilot_defaults_controlled_only() -> None:
    p = MiniDeliveryPilot(pilot_key="pilot-1")
    assert p.controlled_only is True
    assert p.real_llm_enabled is False
    assert p.github_write_enabled is False
    assert p.pr_creation_enabled is False
    assert p.deployment_enabled is False
    assert p.production_executed is False


def test_models_forbid_extra() -> None:
    with pytest.raises(ValidationError):
        MiniDeliveryPilotRequest(unexpected="x")


def test_result_defaults_safe() -> None:
    r = MiniDeliveryPilotResult()
    assert r.production_executed is False
    assert r.github_write_performed is False
    assert r.pr_created is False
    assert r.deployment_performed is False
    assert r.real_llm_used is False


def test_safety_report_defaults() -> None:
    s = SafetyEvidenceReport()
    assert s.status == "safe"
    assert s.production_executed_count == 0
    assert s.chain_of_thought_persisted is False
