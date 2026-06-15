"""Stage 47 -- static checks for a controlled workspace.

Runs ``ruff check .`` when ruff is importable (otherwise classifies it
``skipped`` with a documented reason -- ruff is optional and must not require
the network), and always runs ``compileall`` as an offline fallback.
"""

from __future__ import annotations

import importlib.util

from shared.sdk.workspace_operator.command_runner import DEFAULT_TIMEOUT_SECONDS, run_module
from shared.sdk.workspace_operator.models import WorkspaceTestRun


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def run_ruff(
    workspace_root: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, env: dict | None = None
) -> WorkspaceTestRun:
    if not _available("ruff"):
        return WorkspaceTestRun(
            test_type="ruff",
            command="python -m ruff check .",
            status="skipped",
            output_summary="ruff skipped: ruff is not installed (optional, offline-only)",
            metadata={"skip_reason": "tool_absent"},
        )
    result = run_module("ruff", ["check", "."], cwd=workspace_root, timeout=timeout, env=env)
    combined = f"{result.stdout}\n{result.stderr}".strip()
    status = "passed" if result.exit_code == 0 else ("error" if result.timed_out else "failed")
    return WorkspaceTestRun(
        test_type="ruff",
        command=result.command_str,
        status=status,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        output_summary="\n".join(combined.splitlines()[-15:]),
    )


def run_compileall(
    workspace_root: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, env: dict | None = None
) -> WorkspaceTestRun:
    result = run_module("compileall", ["-q", "."], cwd=workspace_root, timeout=timeout, env=env)
    combined = f"{result.stdout}\n{result.stderr}".strip()
    status = "passed" if result.exit_code == 0 else ("error" if result.timed_out else "failed")
    return WorkspaceTestRun(
        test_type="compileall",
        command=result.command_str,
        status=status,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        output_summary="\n".join(combined.splitlines()[-15:]) or "compileall completed",
    )


def run_static_checks(
    workspace_root: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, env: dict | None = None
) -> list[WorkspaceTestRun]:
    """Run ruff (if available) + compileall; return both runs."""
    return [
        run_ruff(workspace_root, timeout=timeout, env=env),
        run_compileall(workspace_root, timeout=timeout, env=env),
    ]


def overall_static_status(runs: list[WorkspaceTestRun]) -> str:
    """Aggregate static-check status: failed > error > passed > skipped."""
    statuses = {r.status for r in runs}
    if "failed" in statuses:
        return "failed"
    if "error" in statuses:
        return "error"
    if "passed" in statuses:
        return "passed"
    return "skipped"


__all__ = ["run_ruff", "run_compileall", "run_static_checks", "overall_static_status"]
