"""Stage 49 -- no chain-of-thought / raw-prompt persistence anywhere."""

from __future__ import annotations

import json
from pathlib import Path

from delivery_package_fakes import build_fake_package

_REPO = Path(__file__).resolve().parents[1]
_FORBIDDEN = ("chain_of_thought", "raw_prompt", "transcript")


def _strip_sql_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def test_migration_has_no_cot_columns() -> None:
    sql = (_REPO / "migrations" / "021_delivery_package_acceptance_gate.sql").read_text(
        encoding="utf-8"
    )
    code = _strip_sql_comments(sql).lower()
    for term in _FORBIDDEN:
        assert term not in code, term


def test_models_have_no_cot_fields() -> None:
    from shared.sdk.delivery_package import models

    for cls_name in (
        "DeliveryPackage",
        "DeliveryPackageSection",
        "AcceptanceGateRun",
        "HandoffSummary",
        "DeliveryPackageResult",
    ):
        fields = getattr(models, cls_name).model_fields
        for term in _FORBIDDEN:
            assert term not in fields


async def test_persisted_report_has_no_cot(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    blob = json.dumps(
        await stores["package"].get_delivery_package_report(result.package_id)
    ).lower()
    for term in _FORBIDDEN:
        assert term not in blob
