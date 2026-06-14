"""Stage 45 -- brief builder + template detection tests."""

from __future__ import annotations

import pytest

from shared.sdk.project_planning.brief_builder import (
    TEMPLATE_FASTAPI_TODO,
    TEMPLATE_GENERIC,
    build_brief,
    detect_template,
)

FASTAPI_REQUEST = (
    "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
)


@pytest.mark.parametrize(
    "text",
    [
        "Create a FastAPI Todo Service",
        "建立 FastAPI Todo CRUD",
        "幫我做一個 Todo API",
        "FastAPI + SQLite + pytest + README",
    ],
)
def test_detects_fastapi_todo_template(text: str) -> None:
    assert detect_template(text) == TEMPLATE_FASTAPI_TODO


def test_generic_template_for_other_requests() -> None:
    assert detect_template("Build a data pipeline service") == TEMPLATE_GENERIC


def test_fastapi_brief_has_scope_and_non_scope() -> None:
    b = build_brief(FASTAPI_REQUEST)
    assert b.requires_clarification is False
    assert "CRUD Todo API" in b.scope
    assert "authentication" in b.non_scope
    assert b.success_metrics
    assert b.assumptions


def test_vague_request_requires_clarification() -> None:
    b = build_brief("todo")
    assert b.requires_clarification is True
    assert b.scope == []


def test_brief_no_secret_in_output() -> None:
    b = build_brief(FASTAPI_REQUEST)
    blob = " ".join(b.scope + b.non_scope + b.assumptions + b.success_metrics + [b.goal])
    assert "TOKEN" not in blob.upper()
    assert "API_KEY" not in blob.upper()
