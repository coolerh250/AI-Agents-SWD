"""Stage 28 — local validators for the controlled workspace.

These are pure functions that run *after* the deterministic generator
writes files into the workspace. They never execute the generated
code — Python validation is limited to :func:`py_compile.compile`.

Every validator returns ``(ok, reason)`` so they can be composed
trivially by the development-agent. None of them touch the network
or any production resource.
"""

from __future__ import annotations

import os
import py_compile
import tempfile
from typing import Iterable

from shared.sdk.code_workspace.policy import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    validate_allowed_path,
    validate_no_secret_content,
)


def validate_generated_files_exist(
    workspace_path: str, file_paths: Iterable[str]
) -> tuple[bool, str]:
    """Every relative ``file_paths`` entry must exist under ``workspace_path``."""
    if not workspace_path:
        return False, "empty_workspace_path"
    missing: list[str] = []
    for rel in file_paths:
        full = os.path.join(workspace_path, rel)
        if not os.path.isfile(full):
            missing.append(rel)
    if missing:
        return False, f"missing:{','.join(missing[:5])}"
    return True, "all_exist"


def validate_allowlist(
    file_paths: Iterable[str],
    *,
    allowed: Iterable[str] = DEFAULT_ALLOWED_PATHS,
    denied: Iterable[str] = DEFAULT_DENIED_PATHS,
) -> tuple[bool, str]:
    """Every entry must pass :func:`validate_allowed_path`."""
    for rel in file_paths:
        ok, reason = validate_allowed_path(rel, allowed=allowed, denied=denied)
        if not ok:
            return False, f"{rel}:{reason}"
    return True, "all_in_allowlist"


def validate_no_denied_paths(
    file_paths: Iterable[str],
    *,
    denied: Iterable[str] = DEFAULT_DENIED_PATHS,
) -> tuple[bool, str]:
    """Quick denylist-only check (used when allowlist is intentionally relaxed)."""
    for rel in file_paths:
        ok, reason = validate_allowed_path(rel, allowed=("",), denied=denied)
        if not ok and reason.startswith("denied:"):
            return False, f"{rel}:{reason}"
    return True, "no_denied_hits"


def validate_no_secrets(workspace_path: str, file_paths: Iterable[str]) -> tuple[bool, str]:
    """Reject if any generated file contains a secret-looking literal."""
    for rel in file_paths:
        full = os.path.join(workspace_path, rel)
        try:
            with open(full, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        ok, reason = validate_no_secret_content(content)
        if not ok:
            return False, f"{rel}:{reason}"
    return True, "no_secret_signatures"


def _py_compile_one(full_path: str) -> tuple[bool, str]:
    """Wrap ``py_compile.compile`` so a syntax error returns ``(False, reason)``."""
    try:
        # ``doraise=True`` turns SyntaxError into ``PyCompileError``.
        # ``cfile`` to a temp path so we don't litter __pycache__ next
        # to the source — the workspace is short-lived but we keep the
        # filesystem layout untouched.
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as cache_fh:
            cache = cache_fh.name
        try:
            py_compile.compile(full_path, cfile=cache, doraise=True)
        finally:
            try:
                os.unlink(cache)
            except OSError:
                pass
    except py_compile.PyCompileError as exc:
        return False, f"py_compile_error:{exc}"
    except FileNotFoundError:
        return False, "missing_file"
    return True, "py_compile_ok"


def validate_python_syntax_if_py(
    workspace_path: str, file_paths: Iterable[str]
) -> tuple[bool, str]:
    """Run ``py_compile`` on every ``*.py`` file under the workspace."""
    for rel in file_paths:
        if not rel.endswith(".py"):
            continue
        ok, reason = _py_compile_one(os.path.join(workspace_path, rel))
        if not ok:
            return False, f"{rel}:{reason}"
    return True, "all_py_compile_ok"


def validate_tests_syntax_if_py(workspace_path: str, file_paths: Iterable[str]) -> tuple[bool, str]:
    """Tighter version of :func:`validate_python_syntax_if_py` for test files.

    Restricted to entries matching ``tests/`` so the development-agent
    can record a separate counter / status for tests vs app code.
    """
    test_paths = [p for p in file_paths if p.endswith(".py") and "tests/" in p]
    return validate_python_syntax_if_py(workspace_path, test_paths)


def validate_diff_not_empty(diff_text: str) -> tuple[bool, str]:
    """The deterministic generator must produce *some* diff body."""
    if not diff_text or not diff_text.strip():
        return False, "empty_diff"
    if not any(line.startswith("@@") for line in diff_text.splitlines()):
        return False, "no_hunks"
    return True, "diff_non_empty"
