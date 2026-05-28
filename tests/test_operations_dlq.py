"""Tests for /operations/dlq."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_dlq", _ORCH_SRC / "operations.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


def _client(module: ModuleType) -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


@pytest.fixture
def dlq_module(monkeypatch):
    module = _load()

    async def _xinfo_stream(bus: Any, stream: str) -> dict[str, Any]:
        if stream == "stream.deadletter":
            return {
                "name": stream,
                "length": 5,
                "groups": [],
                "consumers": 1,
                "pending": 0,
                "lag": 0,
                "last_delivered_id": "",
                "status": "ok",
            }
        return {
            "name": stream,
            "length": 2,
            "groups": [],
            "consumers": 0,
            "pending": 0,
            "lag": 0,
            "last_delivered_id": "",
            "status": "ok",
        }

    async def _xrevrange_payloads(bus: Any, stream: str, count: int = 50) -> list[dict]:
        if stream == "stream.deadletter":
            return [
                {
                    "id": "1-0",
                    "payload": {
                        "task_id": "t-want",
                        "original_stream": "stream.development",
                        "failure_reason": "boom",
                    },
                },
                {
                    "id": "2-0",
                    "payload": {
                        "task_id": "t-other",
                        "original_stream": "stream.qa",
                    },
                },
            ]
        return [
            {
                "id": "9-0",
                "payload": {
                    "task_id": "t-want",
                    "original_stream": "stream.development",
                    "terminal_failure": True,
                },
            },
        ]

    monkeypatch.setattr(module, "_xinfo_stream", _xinfo_stream)
    monkeypatch.setattr(module, "_xrevrange_payloads", _xrevrange_payloads)
    return module


def test_dlq_unfiltered(dlq_module):
    client = _client(dlq_module)
    response = client.get("/operations/dlq")
    assert response.status_code == 200
    body = response.json()
    assert body["deadletter_length"] == 5
    assert body["deadletter_terminal_length"] == 2
    assert body["deadletter_count"] == 2
    assert body["terminal_count"] == 1


def test_dlq_filtered_by_task_id(dlq_module):
    client = _client(dlq_module)
    response = client.get("/operations/dlq?task_id=t-want")
    assert response.status_code == 200
    body = response.json()
    assert body["deadletter_count"] == 1
    assert body["terminal_count"] == 1
    assert all(entry["payload"]["task_id"] == "t-want" for entry in body["deadletter_events"])


def test_dlq_filtered_by_stream(dlq_module):
    client = _client(dlq_module)
    response = client.get("/operations/dlq?stream=stream.development")
    assert response.status_code == 200
    body = response.json()
    assert all(
        entry["payload"]["original_stream"] == "stream.development"
        for entry in body["deadletter_events"]
    )


def test_dlq_terminal_only(dlq_module):
    client = _client(dlq_module)
    response = client.get("/operations/dlq?terminal=true")
    assert response.status_code == 200
    body = response.json()
    assert "events" in body
    assert body["events"] == body["terminal_events"]
