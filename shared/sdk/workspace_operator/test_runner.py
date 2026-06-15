"""Stage 47 -- run pytest in a controlled workspace and parse the summary.

If pytest (or the generated project's FastAPI/httpx test dependencies) are not
importable by the operator's interpreter, the run is classified ``skipped``
with a documented reason rather than ``failed`` -- we never fail the
environment just because an optional dependency is absent.
"""

from __future__ import annotations

import importlib.util
import re

from shared.sdk.workspace_operator.command_runner import DEFAULT_TIMEOUT_SECONDS, run_module
from shared.sdk.workspace_operator.models import WorkspaceTestRun

# Dependencies the generated FastAPI Todo test suite needs to run.
_REQUIRED_TEST_MODULES = ("pytest", "fastapi", "httpx")

_SUMMARY_RE = re.compile(
    r"(?:(?P<failed>\d+)\s+failed)?[,\s]*(?:(?P<passed>\d+)\s+passed)?", re.IGNORECASE
)


def _missing_modules(modules: tuple[str, ...]) -> list[str]:
    missing = []
    for m in modules:
        try:
            if importlib.util.find_spec(m) is None:
                missing.append(m)
        except (ImportError, ValueError):
            missing.append(m)
    return missing


def _parse_counts(output: str) -> tuple[int | None, int | None]:
    passed = failed = None
    for line in output.splitlines():
        if " passed" in line or " failed" in line:
            m = _SUMMARY_RE.search(line)
            if m:
                if m.group("passed"):
                    passed = int(m.group("passed"))
                if m.group("failed"):
                    failed = int(m.group("failed"))
    return passed, failed


def run_pytest(
    workspace_root: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS, env: dict | None = None
) -> WorkspaceTestRun:
    """Run ``python -m pytest -q`` in the workspace; classify the result."""
    missing = _missing_modules(_REQUIRED_TEST_MODULES)
    if missing:
        return WorkspaceTestRun(
            test_type="pytest",
            command="python -m pytest -q",
            status="skipped",
            output_summary=(
                "pytest skipped: required test dependencies not installed: " + ", ".join(missing)
            ),
            metadata={"missing_dependencies": missing, "skip_reason": "dependency_unavailable"},
        )
    result = run_module("pytest", ["-q"], cwd=workspace_root, timeout=timeout, env=env)
    combined = f"{result.stdout}\n{result.stderr}"
    passed, failed = _parse_counts(combined)
    if result.timed_out:
        status = "error"
    elif result.exit_code == 0:
        status = "passed"
    elif result.exit_code == 5:  # no tests collected
        status = "skipped"
    else:
        status = "failed"
    tail = combined.strip().splitlines()[-15:]
    return WorkspaceTestRun(
        test_type="pytest",
        command=result.command_str,
        status=status,
        exit_code=result.exit_code,
        tests_passed=passed,
        tests_failed=failed,
        tests_total=(None if passed is None and failed is None else (passed or 0) + (failed or 0)),
        duration_ms=result.duration_ms,
        output_summary="\n".join(tail),
    )


__all__ = ["run_pytest"]
