"""Stage 27 — TaskWorkItem / ClarificationRequest / AgentDiscussion dataclasses."""

from __future__ import annotations

from shared.sdk.task_execution import (
    AgentDiscussion,
    ClarificationRequest,
    TaskWorkItem,
)


def test_task_work_item_to_dict_round_trip():
    wi = TaskWorkItem(
        work_item_id="wi-1",
        task_id="t1",
        workflow_id="wf-1",
        title="title",
        description="desc",
        request_type="dev.test",
        execution_mode="delivery_task",
        status="ready_for_development",
        development_required=True,
        github_required=False,
        clarification_required=False,
        execution_plan={"stages": ["intake"]},
        assumptions=["a1"],
        scrum_enabled=False,
    )
    d = wi.to_dict()
    assert d["task_id"] == "t1"
    assert d["execution_mode"] == "delivery_task"
    assert d["status"] == "ready_for_development"
    # JSON fields are concrete python collections — safe to embed in a
    # FastAPI response.
    assert d["execution_plan"]["stages"] == ["intake"]
    assert d["assumptions"] == ["a1"]
    assert d["scrum_enabled"] is False


def test_task_work_item_scrum_optional_for_non_scrum():
    wi = TaskWorkItem(work_item_id="wi-1", task_id="t1")
    d = wi.to_dict()
    # Scrum fields stay optional; the validator and APIs treat None as
    # "not set". Forcing acceptance_criteria/DoD on a non-Scrum task
    # would violate the Stage 27 spec.
    assert d["acceptance_criteria"] is None
    assert d["definition_of_done"] is None
    assert d["scrum_enabled"] is False
    assert d["scrum_metadata"] is None


def test_task_work_item_scrum_full_payload():
    wi = TaskWorkItem(
        work_item_id="wi-1",
        task_id="t1",
        execution_mode="scrum_project",
        scrum_enabled=True,
        acceptance_criteria=["one"],
        definition_of_done=["done"],
        scrum_metadata={"sprint": "alpha"},
    )
    d = wi.to_dict()
    assert d["scrum_enabled"] is True
    assert d["acceptance_criteria"] == ["one"]
    assert d["definition_of_done"] == ["done"]
    assert d["scrum_metadata"] == {"sprint": "alpha"}


def test_agent_discussion_to_dict_carries_message_type():
    disc = AgentDiscussion(
        discussion_id="d-1",
        task_id="t1",
        workflow_id="wf-1",
        agent="qa-agent",
        role="qa",
        message_type="validation_note",
        content="all good",
        confidence=0.7,
        references={"artifact": "test_report"},
    )
    d = disc.to_dict()
    assert d["agent"] == "qa-agent"
    assert d["message_type"] == "validation_note"
    assert d["references"]["artifact"] == "test_report"


def test_clarification_request_to_dict_open():
    c = ClarificationRequest(
        clarification_id="c-1",
        task_id="t1",
        workflow_id="wf-1",
        question="what is the goal?",
    )
    d = c.to_dict()
    assert d["status"] == "open"
    assert d["user_response"] is None
    assert d["answered_at"] is None


def test_clarification_request_to_dict_answered():
    c = ClarificationRequest(
        clarification_id="c-1",
        task_id="t1",
        workflow_id=None,
        question="what is the goal?",
        status="answered",
        user_response="here is the answer",
    )
    d = c.to_dict()
    assert d["status"] == "answered"
    assert d["user_response"] == "here is the answer"
