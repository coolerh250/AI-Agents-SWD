"""Tests for /operations/streams."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_operations_streams", _ORCH_SRC / "operations.py"
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
def streams_module(monkeypatch):
    module = _load()

    async def _xinfo_stream(bus, stream):
        # Mirror the natural state observed in Stage 19: stream.audit has
        # one consumer; stream.notifications has none; everything else is ok.
        if stream == "stream.audit":
            return {
                "name": stream,
                "length": 6047,
                "groups": [
                    {
                        "name": "audit-group",
                        "consumers": 1,
                        "pending": 0,
                        "lag": 0,
                        "last_delivered_id": "1-0",
                    }
                ],
                "consumers": 1,
                "pending": 0,
                "lag": 0,
                "last_delivered_id": "1-0",
                "status": "ok",
            }
        if stream == "stream.notifications":
            return {
                "name": stream,
                "length": 200,
                "groups": [
                    {
                        "name": "notification-group",
                        "consumers": 0,
                        "pending": 0,
                        "lag": 200,
                        "last_delivered_id": "",
                    }
                ],
                "consumers": 0,
                "pending": 0,
                "lag": 200,
                "last_delivered_id": "",
                "status": "informational",
            }
        return {
            "name": stream,
            "length": 0,
            "groups": [
                {
                    "name": "g",
                    "consumers": 1,
                    "pending": 0,
                    "lag": 0,
                    "last_delivered_id": "0-0",
                }
            ],
            "consumers": 1,
            "pending": 0,
            "lag": 0,
            "last_delivered_id": "0-0",
            "status": "ok",
        }

    monkeypatch.setattr(module, "_xinfo_stream", _xinfo_stream)
    return module


def test_streams_endpoint_returns_all_known_streams(streams_module):
    client = _client(streams_module)
    response = client.get("/operations/streams")
    assert response.status_code == 200
    body = response.json()
    names = [s["name"] for s in body["streams"]]
    assert "stream.tasks" in names
    assert "stream.audit" in names
    assert "stream.deadletter" in names
    assert "stream.notifications" in names
    # stream.audit must have at least one consumer in our stub.
    audit = next(s for s in body["streams"] if s["name"] == "stream.audit")
    assert audit["consumers"] >= 1
    # stream.notifications gets the documented design label.
    notif = next(s for s in body["streams"] if s["name"] == "stream.notifications")
    assert notif["status"] == "not_unified_by_design"
    # primary_group is surfaced for every entry.
    for entry in body["streams"]:
        assert "primary_group" in entry
