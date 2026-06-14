"""Stage 46 -- gate evaluation + go/no-go decision (deterministic).

Maps the review context + findings to project review gates, then derives an
overall go/no-go decision. Planning-only this stage: the final decision is
``planning_only`` unless work-item dispatch is enabled (it is not).
"""

from __future__ import annotations

from shared.sdk.design_review.models import (
    DesignReviewDecision,
    DesignReviewFinding,
    GoNoGoSummary,
    ProjectReviewGate,
    ReviewContext,
)

_SEV_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# gate_type -> finding_types that influence it
_GATE_FINDING_TYPES = {
    "requirement_gate": {"requirement_gap", "scope_risk"},
    "architecture_gate": {"architecture_risk"},
    "implementation_strategy_gate": {"implementation_risk", "dependency_issue"},
    "qa_strategy_gate": {"qa_gap", "acceptance_gap"},
    "security_gate": {"security_risk"},
    "delivery_gate": {"delivery_risk"},
}


def _open(findings: list[DesignReviewFinding]) -> list[DesignReviewFinding]:
    return [f for f in findings if f.status == "open"]


def _max_sev(findings: list[DesignReviewFinding]) -> int:
    return max((_SEV_RANK.get(f.severity, 0) for f in findings), default=0)


def _work_types(ctx: ReviewContext) -> set[str]:
    return {str(w.get("work_type") or "") for w in ctx.work_items}


def _structural_ok(gate_type: str, ctx: ReviewContext) -> bool:
    brief = ctx.brief or {}
    wt = _work_types(ctx)
    if gate_type == "requirement_gate":
        return bool(brief.get("scope") and brief.get("non_scope") and ctx.user_stories)
    if gate_type == "architecture_gate":
        return "architecture" in wt or "backend" in wt
    if gate_type == "implementation_strategy_gate":
        has_dev = any(w.get("assigned_agent_role") == "development-agent" for w in ctx.work_items)
        return has_dev and ctx.graph_validation_status != "invalid"
    if gate_type == "qa_strategy_gate":
        return "qa" in wt and bool(ctx.acceptance_criteria)
    if gate_type == "security_gate":
        return True  # always evaluated; status driven by findings
    if gate_type == "delivery_gate":
        titles = " ".join(str(w.get("title") or "") for w in ctx.work_items).lower()
        return "release" in wt or "delivery" in titles
    return True


def evaluate_gates(
    ctx: ReviewContext,
    findings: list[DesignReviewFinding],
    *,
    work_item_dispatch_enabled: bool = False,
) -> list[ProjectReviewGate]:
    gates: list[ProjectReviewGate] = []
    for gate_type, ftypes in _GATE_FINDING_TYPES.items():
        relevant_open = [f for f in _open(findings) if f.finding_type in ftypes]
        sev = _max_sev(relevant_open)
        structural = _structural_ok(gate_type, ctx)
        if sev >= _SEV_RANK["critical"] or not structural:
            status = "blocked"
        elif relevant_open:
            status = "passed_with_findings"
        else:
            status = "passed"
        gates.append(ProjectReviewGate(gate_type=gate_type, status=status))

    # pre_execution_gate: planning-only unless dispatch enabled.
    any_blocked = any(g.status == "blocked" for g in gates)
    if any_blocked:
        pre_status = "blocked"
    elif _open(findings):
        pre_status = "passed_with_findings"
    else:
        pre_status = "passed"
    gates.append(
        ProjectReviewGate(
            gate_type="pre_execution_gate",
            status=pre_status,
            blocking=True,
            metadata={"work_item_dispatch_enabled": work_item_dispatch_enabled},
        )
    )
    return gates


def decide_go_no_go(
    ctx: ReviewContext,
    findings: list[DesignReviewFinding],
    gates: list[ProjectReviewGate],
    *,
    planning_only: bool = True,
    work_item_dispatch_enabled: bool = False,
) -> tuple[str, str, GoNoGoSummary]:
    """Return (review_status, decision, GoNoGoSummary)."""
    open_findings = _open(findings)
    blocking = [f for f in open_findings if f.severity in ("high", "critical")]
    critical = [f for f in open_findings if f.severity == "critical"]
    any_gate_blocked = any(g.status == "blocked" for g in gates)
    gates_passed = sum(1 for g in gates if g.status in ("passed", "passed_with_findings"))

    needs_clarification = any(
        f.finding_type == "requirement_gap" and f.severity in ("high", "critical")
        for f in open_findings
    )

    if critical or any_gate_blocked:
        status, decision = "blocked", "no_go"
    elif needs_clarification:
        status, decision = "blocked", "needs_clarification"
    elif planning_only or not work_item_dispatch_enabled:
        status = "passed_with_findings" if open_findings else "passed"
        decision = "planning_only"
    else:
        status = "passed_with_findings" if open_findings else "passed"
        decision = "go_with_findings" if open_findings else "go"

    summary = GoNoGoSummary(
        decision=decision,
        blocking_findings_count=len(blocking),
        total_findings_count=len(findings),
        gates_passed=gates_passed,
        gates_total=len(gates),
        next_suggested_stage=(
            "resolve_blockers"
            if decision in ("no_go", "needs_clarification")
            else "real_repo_workspace_operator"
        ),
        planning_only=planning_only,
        production_executed=False,
    )
    return status, decision, summary


def build_decisions(
    decision: str,
    summary: GoNoGoSummary,
) -> list[DesignReviewDecision]:
    return [
        DesignReviewDecision(
            decision_type="go_no_go_decision",
            decision=decision,
            rationale_summary=(
                f"{summary.gates_passed}/{summary.gates_total} gates passed; "
                f"{summary.blocking_findings_count} blocking findings; planning-only="
                f"{summary.planning_only}."
            ),
            approval_required=False,
            approval_status="not_required",
        ),
        DesignReviewDecision(
            decision_type="delivery_decision",
            decision="defer_to_delivery_pilot",
            rationale_summary="Execution/delivery deferred; work-item dispatch disabled.",
        ),
    ]


__all__ = ["evaluate_gates", "decide_go_no_go", "build_decisions"]
