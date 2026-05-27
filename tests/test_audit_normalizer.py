"""Unit tests for shared.sdk.audit.normalizer."""

from __future__ import annotations

import json

from shared.sdk.audit.normalizer import (
    is_audit_recorded_echo,
    normalize_audit_event,
)


def test_normalize_stream_agent_audit_dict():
    event = {
        "task_id": "t1",
        "agent": "intake-agent",
        "decision_type": "intake",
        "summary": "intake done",
        "result": "ok",
        "artifact_refs": {"x": 1},
        "created_at": "2026-05-27T00:00:00+00:00",
    }
    out = normalize_audit_event(event, source_message_id="1-0")
    assert out["task_id"] == "t1"
    assert out["agent"] == "intake-agent"
    assert out["decision_type"] == "intake"
    assert out["summary"] == "intake done"
    assert out["result"] == "ok"
    assert out["created_at"] == "2026-05-27T00:00:00+00:00"
    assert out["artifact_refs"]["x"] == 1
    assert out["artifact_refs"]["source_message_id"] == "1-0"
    assert out["artifact_refs"]["source_stream"] == "stream.audit"
    assert out["artifact_refs"]["normalized_by"] == "audit-worker"


def test_normalize_falls_back_to_event_then_unknown():
    out = normalize_audit_event({"event": "github.demo_pr.dry_run"})
    assert out["decision_type"] == "github.demo_pr.dry_run"
    assert out["agent"] == "unknown"
    assert out["task_id"] == "unknown"
    assert out["result"] == "recorded"
    assert out["summary"]  # never empty


def test_normalize_event_type_and_summary_fallbacks():
    out = normalize_audit_event(
        {
            "event_type": "github_pr_integration",
            "message": "deploy ok",
            "status": "success",
        }
    )
    assert out["decision_type"] == "github_pr_integration"
    assert out["summary"] == "deploy ok"
    assert out["result"] == "success"


def test_normalize_handles_nested_payload_dict():
    raw = {
        "event": "audit.write",
        "payload": {
            "task_id": "nested",
            "agent": "qa-agent",
            "decision_type": "qa",
            "summary": "tests ok",
            "result": "ok",
        },
    }
    out = normalize_audit_event(raw)
    assert out["task_id"] == "nested"
    assert out["agent"] == "qa-agent"
    assert out["decision_type"] == "qa"


def test_normalize_handles_json_string_data():
    raw = {
        "data": json.dumps(
            {
                "task_id": "from-string",
                "agent": "development-agent",
                "decision_type": "development",
                "summary": "built",
                "result": "ok",
            }
        )
    }
    out = normalize_audit_event(raw)
    assert out["task_id"] == "from-string"
    assert out["agent"] == "development-agent"
    assert out["decision_type"] == "development"


def test_normalize_preserves_existing_artifact_provenance():
    raw = {
        "task_id": "t",
        "agent": "x",
        "decision_type": "d",
        "summary": "s",
        "result": "r",
        "artifact_refs": {
            "source_message_id": "explicit",
            "source_stream": "stream.other",
            "normalized_by": "external",
            "original_event": {"foo": "bar"},
        },
    }
    out = normalize_audit_event(raw, source_message_id="1-1")
    # Existing provenance is NOT overwritten.
    assert out["artifact_refs"]["source_message_id"] == "explicit"
    assert out["artifact_refs"]["source_stream"] == "stream.other"
    assert out["artifact_refs"]["normalized_by"] == "external"
    assert out["artifact_refs"]["original_event"] == {"foo": "bar"}


def test_audit_recorded_echo_detected_by_event():
    assert is_audit_recorded_echo({"event": "audit.recorded", "audit_id": "abc"})
    assert is_audit_recorded_echo({"event_type": "audit.recorded"})


def test_audit_recorded_echo_detected_by_decision_type():
    assert is_audit_recorded_echo({"decision_type": "audit_recorded"})


def test_audit_recorded_echo_detected_by_audit_service_id():
    assert is_audit_recorded_echo({"agent": "audit-service", "audit_id": "abc-123"})


def test_audit_recorded_echo_negative_for_normal_event():
    assert not is_audit_recorded_echo(
        {
            "agent": "intake-agent",
            "decision_type": "intake",
            "summary": "ok",
            "result": "ok",
        }
    )


def test_normalize_uses_workflow_id_when_task_id_missing():
    out = normalize_audit_event({"workflow_id": "wf-only", "agent": "x", "decision_type": "d"})
    assert out["task_id"] == "wf-only"
