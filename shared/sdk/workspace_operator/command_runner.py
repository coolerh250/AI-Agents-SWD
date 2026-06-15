"""Stage 47 -- allowlisted command runner for controlled workspaces.

Only a fixed set of ``python -m <module>`` invocations are permitted, always
with ``shell=False`` (argv list, never a shell string), a fixed working
directory pinned to a validated workspace root, a mandatory timeout, and
secret-redacted output summaries. There is no path for arbitrary commands and
no string interpolation into a shell.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field

from shared.sdk.workspace_operator.path_safety import validate_workspace_root
from shared.sdk.workspace_operator.safety import redact

# Only these ``python -m <module>`` modules may be executed in a workspace.
ALLOWED_MODULES: tuple[str, ...] = ("pytest", "ruff", "compileall", "py_compile")

DEFAULT_TIMEOUT_SECONDS = 120


class CommandPolicyError(ValueError):
    """Raised when a command is not on the allowlist."""


@dataclass
class CommandResult:
    module: str
    argv: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def command_str(self) -> str:
        return "python -m " + " ".join(self.argv[2:])


def run_module(
    module: str,
    args: list[str] | None = None,
    *,
    cwd: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env: dict | None = None,
) -> CommandResult:
    """Run ``python -m <module> <args>`` inside the validated workspace ``cwd``.

    ``cwd`` must resolve under an allowlisted workspace root. Output is captured
    and redacted; secrets never reach the returned summary.
    """
    if module not in ALLOWED_MODULES:
        raise CommandPolicyError(f"module not allowed: {module!r}")
    args = list(args or [])
    if any(a.startswith("-") and ";" in a for a in args):  # defensive
        raise CommandPolicyError("unsafe argument detected")
    safe_cwd = validate_workspace_root(cwd, env=env)
    argv = [sys.executable, "-m", module, *args]
    started = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(  # noqa: S603 -- shell=False, fixed argv, pinned cwd
            argv,
            cwd=safe_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = -1
        stdout = exc.stdout or "" if isinstance(exc.stdout, str) else ""
        stderr = "command timed out"
    duration_ms = int((time.perf_counter() - started) * 1000)
    return CommandResult(
        module=module,
        argv=argv,
        exit_code=exit_code,
        stdout=redact(stdout),
        stderr=redact(stderr),
        duration_ms=duration_ms,
        timed_out=timed_out,
    )


__all__ = [
    "ALLOWED_MODULES",
    "DEFAULT_TIMEOUT_SECONDS",
    "CommandPolicyError",
    "CommandResult",
    "run_module",
]
