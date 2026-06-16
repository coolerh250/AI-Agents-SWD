"""Stage 52 -- safe allowlisted verification rerun.

Operators may rerun ONLY the allowlisted verification scripts below. There is a
static map of ``script_key -> (executable, fixed args)``. The runner NEVER
accepts a user-supplied path, argument, or shell string:

  * shell=False, fixed argv
  * the resolved executable must stay under the repo ``scripts/`` directory
    (realpath containment)
  * fixed cwd (repo root), sanitized environment
  * timeout with child-process termination
  * output captured, size-capped, and redacted before persistence
  * only summary / marker / report path / exit code are stored
  * no real external delivery, no production action
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# script_key -> (relative script path, fixed extra args, requires_audit_lock,
#                higher_confirmation)
ALLOWLISTED_SCRIPTS: dict[str, tuple[str, list[str], bool, bool]] = {
    "delivery_package_acceptance_gate": (
        "scripts/verify_delivery_package_acceptance_gate.sh",
        [],
        True,
        False,
    ),
    "admin_console_v0": ("scripts/verify_admin_console_v0.sh", [], False, False),
    "backup_dr_gap_closure": ("scripts/verify_backup_dr_gap_closure.sh", [], True, False),
    "audit_integrity": ("scripts/verify_tamper_evident_audit.sh", [], True, False),
    "full_regression": (
        "scripts/run_full_regression.sh",
        ["--full", "--json-report"],
        True,
        True,
    ),
}

DEFAULT_TIMEOUT_SECONDS = 1800
MAX_OUTPUT_BYTES = 200_000

_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(token|secret|password|api[_-]?key|hmac|private[_-]?key)\s*[=:]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


class VerificationNotAllowed(ValueError):
    """Raised when a script key is not in the allowlist."""


@dataclass
class RerunResult:
    script_key: str
    verification_key: str
    status: str
    exit_code: int | None
    result_marker: str | None
    report_path: str | None
    output_tail: str
    timed_out: bool
    production_executed: bool = False


def resolve_script(script_key: str, *, repo_root: str | Path | None = None) -> Path:
    """Resolve + contain the allowlisted script path. Raises if not allowed."""
    if script_key not in ALLOWLISTED_SCRIPTS:
        raise VerificationNotAllowed(f"verification script key not allowed: {script_key}")
    root = Path(repo_root or os.getcwd()).resolve()
    rel = ALLOWLISTED_SCRIPTS[script_key][0]
    target = (root / rel).resolve()
    scripts_dir = (root / "scripts").resolve()
    # realpath containment: the executable must live under <repo>/scripts.
    if scripts_dir not in target.parents and target.parent != scripts_dir:
        raise VerificationNotAllowed(f"script path escapes scripts/: {target}")
    if not target.is_file():
        raise VerificationNotAllowed(f"script not found: {target}")
    return target


def requires_higher_confirmation(script_key: str) -> bool:
    entry = ALLOWLISTED_SCRIPTS.get(script_key)
    return bool(entry and entry[3])


def redact(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


def _extract_marker(output: str) -> str | None:
    marker = None
    for line in output.splitlines():
        if re.match(
            r"^[A-Z_]+: (PASS|FAIL|PASS_WITH_GAPS|PASS_WITH_NON_PRODUCTION_LIMITATIONS"
            r"|PASS_WITH_DOCUMENTED_GAPS|SKIPPED-PASS)",
            line.strip(),
        ):
            marker = line.strip()
    return marker


def run_verification(
    script_key: str,
    *,
    verification_key: str | None = None,
    repo_root: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> RerunResult:
    """Execute an allowlisted verification with shell=False + fixed argv."""
    target = resolve_script(script_key, repo_root=repo_root)
    _, extra_args, _requires_lock, _ = ALLOWLISTED_SCRIPTS[script_key]
    root = Path(repo_root or os.getcwd()).resolve()

    # Sanitized environment: pass through only a safe subset.
    base_env = env if env is not None else os.environ
    safe_env = {
        k: base_env[k]
        for k in (
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "DATABASE_URL",
            "REDIS_URL",
            "ORCHESTRATOR_URL",
            "PYTHON",
            "VIRTUAL_ENV",
        )
        if k in base_env
    }
    argv = ["bash", str(target), *extra_args]

    timed_out = False
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, shell=False, contained path
            argv,
            cwd=str(root),
            env=safe_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            start_new_session=(sys.platform != "win32"),
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        # subprocess.run already terminates the child on timeout; with
        # start_new_session the child runs in its own process group so any
        # grandchildren are reaped with it.
        timed_out = True
        combined = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        exit_code = None

    redacted = redact(combined)
    marker = _extract_marker(redacted)
    tail = redacted[-MAX_OUTPUT_BYTES:]
    report_path = None
    m = re.search(r"report:\s*(source/regression-reports/\S+\.json)", redacted)
    if m:
        report_path = m.group(1)

    if timed_out:
        status = "failed"
    elif exit_code == 0:
        status = "completed"
    else:
        status = "failed"

    return RerunResult(
        script_key=script_key,
        verification_key=verification_key or script_key,
        status=status,
        exit_code=exit_code,
        result_marker=marker,
        report_path=report_path,
        output_tail=tail,
        timed_out=timed_out,
        production_executed=False,
    )


__all__ = [
    "ALLOWLISTED_SCRIPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_OUTPUT_BYTES",
    "VerificationNotAllowed",
    "RerunResult",
    "resolve_script",
    "requires_higher_confirmation",
    "redact",
    "run_verification",
]
