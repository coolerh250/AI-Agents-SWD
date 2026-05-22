import uuid

import pytest

from shared.sdk.agent_execution.store import AgentExecutionStore

_DB_SKIP = "no reachable PostgreSQL; skipping agent execution store test"


async def _store_or_skip() -> AgentExecutionStore:
    store = AgentExecutionStore()
    try:
        await store.list_executions(task_id="__connectivity_probe__")
    except Exception:
        pytest.skip(_DB_SKIP)
    return store


def _task_id() -> str:
    return f"test-exec-{uuid.uuid4().hex[:8]}"


async def test_create_execution_starts_record():
    store = await _store_or_skip()
    task_id = _task_id()
    execution = await store.create_execution(task_id, "intake-agent")
    assert execution["execution_id"]
    assert execution["task_id"] == task_id
    assert execution["agent"] == "intake-agent"
    assert execution["status"] == "started"
    assert execution["started_at"]


async def test_complete_execution():
    store = await _store_or_skip()
    execution = await store.create_execution(_task_id(), "qa-agent")
    completed = await store.complete_execution(execution["execution_id"], metadata={"k": "v"})
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["completed_at"]
    assert completed["metadata"] == {"k": "v"}


async def test_fail_execution():
    store = await _store_or_skip()
    execution = await store.create_execution(_task_id(), "devops-agent")
    failed = await store.fail_execution(execution["execution_id"], "boom")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["error"] == "boom"


async def test_update_and_get_execution():
    store = await _store_or_skip()
    execution = await store.create_execution(_task_id(), "development-agent")
    await store.update_execution(execution["execution_id"], status="running")
    fetched = await store.get_execution(execution["execution_id"])
    assert fetched is not None
    assert fetched["status"] == "running"


async def test_list_executions_filters():
    store = await _store_or_skip()
    task_id = _task_id()
    await store.create_execution(task_id, "intake-agent")
    by_task = await store.list_executions(task_id=task_id)
    assert len(by_task) >= 1
    by_agent = await store.list_executions(task_id=task_id, agent="intake-agent")
    assert by_agent and all(e["agent"] == "intake-agent" for e in by_agent)
    assert await store.list_executions(task_id=task_id, agent="missing-agent") == []
