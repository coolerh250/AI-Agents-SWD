"""Stage 48 -- build a safety / governance evidence report for a pilot."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import SafetyEvidenceReport
from shared.sdk.workspace_operator.safety import contains_secret


def build_safety_report(
    *,
    workspace_result: dict | None,
    report_text_blobs: list[str] | None = None,
) -> SafetyEvidenceReport:
    """Assert the controlled-only posture from the workspace execution result.

    Any high-risk flag (production_executed / github_write / pr / deploy /
    real_llm / external delivery / repo-root write / secret leak / CoT) flips
    the status to ``blocked``.
    """
    ws = workspace_result or {}
    github_write = bool(ws.get("github_write_performed", False))
    repo_write = bool(ws.get("repo_write_performed", False))
    deploy = bool(ws.get("deployment_performed", False))
    real_llm = bool(ws.get("real_llm_used", False))
    production = bool(ws.get("production_executed", False))

    secret_leak = any(contains_secret(b) for b in (report_text_blobs or []))

    findings: list = []
    high_risk = False
    for label, value in (
        ("production_executed", production),
        ("github_write_performed", github_write),
        ("repo_root_modified", repo_write),
        ("deployment_performed", deploy),
        ("real_llm_used", real_llm),
        ("secret_leak_detected", secret_leak),
    ):
        if value:
            high_risk = True
            findings.append({"type": "safety", "flag": label, "detail": f"{label}=true"})

    status = "blocked" if high_risk else "safe"
    summary = (
        "controlled-only: no production execution, no GitHub write, no PR, no deploy, "
        "no real LLM, no external delivery, no secret leak, no chain-of-thought."
        if not high_risk
        else "blocked: a high-risk action flag was set true."
    )
    return SafetyEvidenceReport(
        status=status,
        production_executed_count=0,
        github_write_performed=github_write,
        pr_created=False,
        deployment_performed=deploy,
        real_llm_used=real_llm,
        real_external_delivery_performed=False,
        repo_root_modified=repo_write,
        secret_leak_detected=secret_leak,
        chain_of_thought_persisted=False,
        findings=findings,
        report_summary=summary,
    )


__all__ = ["build_safety_report"]
