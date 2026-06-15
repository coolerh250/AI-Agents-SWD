"""Stage 47 -- work item -> execution link mapping."""

from __future__ import annotations

from shared.sdk.workspace_operator.work_item_mapper import map_work_items

WORK_ITEMS = [
    {"id": "i-req", "work_item_key": "REQ-001", "work_type": "requirement"},
    {"id": "i-arch", "work_item_key": "ARCH-001", "work_type": "architecture"},
    {"id": "i-be1", "work_item_key": "BE-001", "work_type": "backend"},
    {"id": "i-be2", "work_item_key": "BE-002", "work_type": "backend"},
    {"id": "i-db", "work_item_key": "DB-001", "work_type": "database"},
    {"id": "i-qa1", "work_item_key": "QA-001", "work_type": "qa"},
    {"id": "i-doc", "work_item_key": "DOC-001", "work_type": "documentation"},
    {"id": "i-qa2", "work_item_key": "QA-002", "work_type": "qa"},
    {"id": "i-del", "work_item_key": "DEL-001", "work_type": "release"},
]


def _by_key(links):
    return {link.work_item_key: link.execution_status for link in links}


def test_mapping_when_tests_pass() -> None:
    links = map_work_items(WORK_ITEMS, tests_status="passed", evidence_artifact_id="a1")
    status = _by_key(links)
    assert status["REQ-001"] == "generated"
    assert status["ARCH-001"] == "generated"
    assert status["DOC-001"] == "generated"
    assert status["BE-001"] == "tested"
    assert status["DB-001"] == "tested"
    assert status["QA-001"] == "tested"
    assert status["QA-002"] == "passed"
    assert status["DEL-001"] == "pending"
    assert all(link.evidence_artifact_id == "a1" for link in links)


def test_mapping_when_tests_fail() -> None:
    status = _by_key(map_work_items(WORK_ITEMS, tests_status="failed"))
    assert status["QA-002"] == "failed"
    assert status["BE-002"] == "generated"  # not tested when tests fail


def test_skips_items_without_id() -> None:
    links = map_work_items([{"work_item_key": "X"}], tests_status="passed")
    assert links == []
