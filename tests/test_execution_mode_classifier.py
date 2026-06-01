"""Stage 27 — deterministic execution-mode classifier."""

from __future__ import annotations

from shared.sdk.task_execution import classify_execution_mode
from shared.sdk.task_execution.mode_classifier import needs_clarification_signals


def test_classify_simple_task_default():
    r = classify_execution_mode(
        request_type="general",
        description="please tidy up the docs introduction",
    )
    assert r.execution_mode == "simple_task"
    assert r.scrum_enabled is False
    assert r.development_required is False
    assert r.github_required is False
    assert r.clarification_required is False


def test_classify_delivery_task_dev_keyword():
    r = classify_execution_mode(
        request_type="dev.test",
        description="implement a new /healthz endpoint and add a test",
    )
    assert r.execution_mode == "delivery_task"
    assert r.development_required is True
    # No Scrum unless explicit keyword.
    assert r.scrum_enabled is False


def test_classify_delivery_task_request_type_fallback():
    # No dev keyword in the description, but the dev.* request_type
    # is enough to route to delivery_task.
    r = classify_execution_mode(
        request_type="dev.test",
        description="this entry is short on prose but has enough context",
    )
    assert r.execution_mode == "delivery_task"


def test_classify_scrum_project_explicit_keyword():
    r = classify_execution_mode(
        request_type="general",
        description=(
            "Project kickoff for the alpha sprint — please populate the backlog, "
            "author the acceptance criteria, and pin the definition of done."
        ),
    )
    assert r.execution_mode == "scrum_project"
    assert r.scrum_enabled is True
    assert r.development_required is True


def test_classify_scrum_does_not_promote_delivery():
    r = classify_execution_mode(
        request_type="general", description="add a new endpoint to fix a bug"
    )
    assert r.execution_mode == "delivery_task"
    assert r.scrum_enabled is False
    assert "Scrum" not in r.reason and "scrum" not in r.reason


def test_classify_clarification_short_description():
    r = classify_execution_mode(request_type="general", description="TBD")
    assert r.clarification_required is True


def test_classify_clarification_signal_tbd():
    r = classify_execution_mode(
        request_type="general",
        description="please add an endpoint, details TBD",
    )
    assert r.clarification_required is True


def test_classify_github_required_via_options():
    r = classify_execution_mode(
        request_type="general",
        description="prepare a PR with the new docs section",
        github_options={"enabled": True},
    )
    assert r.github_required is True


def test_explicit_mode_short_circuits():
    r = classify_execution_mode(
        request_type="dev.test",
        description="implement a feature",
        explicit_mode="simple_task",
    )
    assert r.execution_mode == "simple_task"
    assert r.scrum_enabled is False


def test_needs_clarification_signal_helper_long_description():
    needed, _ = needs_clarification_signals("this is a clearly stated dev task")
    assert needed is False


def test_needs_clarification_signal_helper_question_mark():
    needed, reason = needs_clarification_signals("really need this ?")
    assert needed is True
    assert reason.startswith("signal:")
