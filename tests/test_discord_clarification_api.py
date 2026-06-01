"""Stage 27 — Discord-gateway /discord/clarifications endpoints."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_discord_main() -> ModuleType:
    src = _REPO_ROOT / "apps" / "discord-gateway" / "src"
    sys.path.insert(0, str(src))
    try:
        for name in ("client", "parser"):
            path = src / f"{name}.py"
            if not path.exists():
                continue
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault(name, mod)
            spec.loader.exec_module(mod)
        spec = importlib.util.spec_from_file_location("discord_gateway_main", src / "main.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


@pytest.fixture(scope="module")
def dg():
    try:
        return _load_discord_main()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"discord-gateway main not loadable: {exc}")


class _Clar:
    def __init__(self, *, status="open", task_id="t1", user_response=None):
        self.clarification_id = "c-1"
        self.task_id = task_id
        self.status = status
        self.user_response = user_response

    def to_dict(self):
        return {
            "clarification_id": self.clarification_id,
            "task_id": self.task_id,
            "status": self.status,
            "user_response": self.user_response,
        }


class _WI:
    def __init__(self):
        self.task_id = "t1"
        self.status = "needs_clarification"

    def to_dict(self):
        return {"task_id": self.task_id, "status": self.status}


class _FakeStore:
    def __init__(
        self,
        *,
        clar_existing: _Clar | None = None,
        clar_after_answer: _Clar | None = None,
        clar_list: list[_Clar] | None = None,
        work_item: _WI | None = None,
    ):
        self._clar_existing = clar_existing
        self._clar_after_answer = clar_after_answer
        self._clar_list = clar_list or []
        self._work_item = work_item

    async def list_clarification_requests(self, task_id, *, status=None):
        if status is None:
            return list(self._clar_list)
        return [c for c in self._clar_list if c.status == status]

    async def get_work_item(self, task_id):
        return self._work_item

    async def get_clarification_request(self, clarification_id):
        return self._clar_existing

    async def answer_clarification_request(self, clarification_id, **kwargs):
        return self._clar_after_answer


def _patch_noop_publish(dg, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(dg, "_publish_notification", _noop)
    monkeypatch.setattr(dg, "_publish_audit", _noop)


def test_list_clarifications_returns_open_count(dg, monkeypatch):
    fake = _FakeStore(
        clar_list=[_Clar(status="open"), _Clar(status="answered")],
        work_item=_WI(),
    )
    monkeypatch.setattr(dg, "TaskExecutionStore", lambda: fake)
    client = TestClient(dg.app)
    r = client.get("/discord/clarifications/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["open_count"] == 1
    assert body["work_item"]["task_id"] == "t1"


def test_answer_clarification_404_when_missing(dg, monkeypatch):
    fake = _FakeStore(clar_existing=None)
    monkeypatch.setattr(dg, "TaskExecutionStore", lambda: fake)
    client = TestClient(dg.app)
    r = client.post(
        "/discord/clarifications/c-1/answer",
        json={"answer": "here is the answer", "user_id": "u1"},
    )
    assert r.status_code == 404


def test_answer_clarification_already_answered_short_circuits(dg, monkeypatch):
    fake = _FakeStore(clar_existing=_Clar(status="answered", user_response="prior"))
    monkeypatch.setattr(dg, "TaskExecutionStore", lambda: fake)
    client = TestClient(dg.app)
    r = client.post(
        "/discord/clarifications/c-1/answer",
        json={"answer": "again", "user_id": "u1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["already_answered"] is True
    assert body["status"] == "answered"


def test_answer_clarification_happy_path_resumes(dg, monkeypatch):
    fake = _FakeStore(
        clar_existing=_Clar(status="open"),
        clar_after_answer=_Clar(status="answered", user_response="the answer"),
    )
    monkeypatch.setattr(dg, "TaskExecutionStore", lambda: fake)
    _patch_noop_publish(dg, monkeypatch)

    class _FakeHttpxResp:
        status_code = 200

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url):
            return _FakeHttpxResp()

    monkeypatch.setattr(dg.httpx, "AsyncClient", _FakeAsyncClient)

    client = TestClient(dg.app)
    r = client.post(
        "/discord/clarifications/c-1/answer",
        json={"answer": "the answer", "user_id": "u1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered"
    assert body["sandbox"] is True
    assert body["resume_status"] == "ok"
