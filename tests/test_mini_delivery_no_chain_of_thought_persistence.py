"""Stage 48 -- no chain-of-thought / raw-prompt persistence anywhere."""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("chain_of_thought", "raw_prompt", "transcript")
# ``chain_of_thought_persisted`` is a governance SAFETY-ASSERTION boolean
# (always false) -- it records that NO chain-of-thought was persisted; it is
# NOT a column that stores chain-of-thought content.
_ALLOWED = ("chain_of_thought_persisted",)


def _strip_sql_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def test_migration_has_no_cot_columns() -> None:
    sql = (_REPO / "migrations" / "020_mini_project_delivery_pilot.sql").read_text(encoding="utf-8")
    code = _strip_sql_comments(sql).lower()
    for allowed in _ALLOWED:
        code = code.replace(allowed, "")
    for term in _FORBIDDEN:
        assert term not in code, term


def test_models_have_no_cot_fields() -> None:
    from shared.sdk.mini_delivery_pilot import models

    for cls_name in (
        "MiniDeliveryPilot",
        "MiniDeliveryReport",
        "MiniDeliveryPilotResult",
        "AcceptanceEvaluation",
    ):
        fields = getattr(models, cls_name).model_fields
        for term in _FORBIDDEN:
            assert term not in fields


def test_safety_report_tracks_cot_persisted_false() -> None:
    from shared.sdk.mini_delivery_pilot.safety_evidence_builder import build_safety_report

    s = build_safety_report(workspace_result={"production_executed": False})
    assert s.chain_of_thought_persisted is False
