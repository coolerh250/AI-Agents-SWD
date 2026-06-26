"""Step 57 -- project / work-item audit mapping + redaction."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.work_items.events import build_audit_metadata

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "infra" / "delivery" / "project-work-item-audit-mapping.yaml"


def test_mapping_events_and_required_metadata() -> None:
    d = (yaml.safe_load(MAP.read_text(encoding="utf-8")) or {})["projectWorkItemAuditMapping"]
    assert {"project_created", "work_item_dispatched", "delivery_package_linked"} <= set(
        d["events"]
    )
    assert {"actor", "role", "reason", "project_id", "correlation_id"} <= set(d["requiredMetadata"])
    assert {"secret", "token", "chain_of_thought"} <= set(d["forbiddenMetadata"])


def test_metadata_redacts_forbidden_keys() -> None:
    meta = build_audit_metadata(
        event_type="work_item_dispatched",
        actor="a",
        role="operator",
        reason="r",
        project_id="p",
        work_item_id="w",
        correlation_id="c",
        extra={"secret": "x", "chain_of_thought": "y", "safe": 1},
    )
    assert "secret" not in meta and "chain_of_thought" not in meta
    assert meta["safe"] == 1
    assert meta["production_executed"] is False
