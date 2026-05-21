import pytest

from shared.sdk.base_agent.base import BaseAgent


class DummyAgent(BaseAgent):
    name = "dummy-agent"
    allowed_tools = ["noop"]

    async def receive_task(self, task: dict) -> dict:
        return {"received": task}

    async def analyze(self, context: dict) -> dict:
        return {"analysis": context}

    async def execute(self, plan: dict) -> dict:
        return {"executed": plan}


def test_base_agent_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


def test_dummy_agent_instantiates():
    agent = DummyAgent()
    assert agent.name == "dummy-agent"
    assert agent.allowed_tools == ["noop"]


async def test_dummy_agent_abstract_methods():
    agent = DummyAgent()
    assert (await agent.receive_task({"id": "t1"}))["received"] == {"id": "t1"}
    assert (await agent.analyze({"k": "v"}))["analysis"] == {"k": "v"}
    assert (await agent.execute({"step": 1}))["executed"] == {"step": 1}


async def test_request_approval_non_restricted():
    agent = DummyAgent()
    result = await agent.request_approval({"type": "code.read"})
    assert result["allowed"] is True
    assert result["approval_required"] is False


async def test_request_approval_restricted():
    agent = DummyAgent()
    result = await agent.request_approval({"type": "production.deploy"})
    assert result["allowed"] is False
    assert result["approval_required"] is True


async def test_write_audit_without_event_bus():
    agent = DummyAgent()
    await agent.write_audit(
        {"decision_type": "test", "summary": "s", "result": "ok"}
    )


async def test_report_stores_last_result():
    agent = DummyAgent()
    await agent.report({"status": "done"})
    assert agent.last_report == {"status": "done"}
