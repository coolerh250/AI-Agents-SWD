"""Stage 46 -- gate evaluator + go/no-go tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.review_builder import build_review


def test_fastapi_todo_planning_only_or_go_with_findings() -> None:
    r = build_review(build_fastapi_todo_context(), planning_only=True)
    assert r.decision in ("planning_only", "go_with_findings", "go")
    assert r.summary.blocking_findings_count == 0
    # no critical findings for the valid template
    assert not any(f.severity == "critical" for f in r.findings)


def test_fastapi_todo_expected_gates() -> None:
    r = build_review(build_fastapi_todo_context(), planning_only=True)
    by = {g.gate_type: g.status for g in r.gates}
    assert by["requirement_gate"] == "passed"
    assert by["architecture_gate"] == "passed"
    assert by["implementation_strategy_gate"] == "passed"
    assert by["qa_strategy_gate"] == "passed"
    assert by["security_gate"] == "passed_with_findings"
    assert by["delivery_gate"] == "passed"
    assert by["pre_execution_gate"] in ("passed_with_findings", "passed")
    assert len(r.gates) >= 6


def test_invalid_graph_no_go() -> None:
    r = build_review(
        build_fastapi_todo_context(graph_validation_status="invalid"), planning_only=True
    )
    assert r.decision == "no_go"
    assert r.status == "blocked"


def test_dispatch_enabled_go_with_findings() -> None:
    # When dispatch is enabled (future), the valid template yields go_with_findings.
    r = build_review(
        build_fastapi_todo_context(), planning_only=False, work_item_dispatch_enabled=True
    )
    assert r.decision in ("go_with_findings", "go")
