"""Stage 41 -- verify_env.sh helper existence and structure."""

from pathlib import Path


VERIFY_ENV_PATH = Path("scripts/lib/verify_env.sh")
REQUIRED_FUNCTIONS = [
    "require_venv_python",
    "require_command",
    "require_python_module",
    "run_python",
    "run_in_service",
    "print_verify_header",
    "print_verify_result",
    "fail_with_marker",
    "skip_with_marker",
    "detect_host_dependency_leak",
    "redact_env_values",
]
REQUIRED_EXPORTS = ["REPO_ROOT", "VENV_PYTHON", "PYTHON"]


def test_verify_env_helper_exists():
    assert VERIFY_ENV_PATH.is_file(), f"Missing: {VERIFY_ENV_PATH}"


def test_verify_env_helper_is_shell():
    content = VERIFY_ENV_PATH.read_text()
    assert content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash"), (
        "verify_env.sh must start with bash shebang"
    )


def test_verify_env_exports_python():
    content = VERIFY_ENV_PATH.read_text()
    # exports can be individual "export PYTHON=..." or combined "export A B C"
    assert 'PYTHON' in content and 'export' in content, "verify_env.sh must export PYTHON"
    assert 'VENV_PYTHON' in content, "verify_env.sh must reference VENV_PYTHON"
    assert 'REPO_ROOT' in content, "verify_env.sh must reference REPO_ROOT"
    # Check that the final export line covers all three
    assert 'export REPO_ROOT VENV_PYTHON PYTHON' in content or all(
        f'export {v}' in content for v in ['PYTHON', 'VENV_PYTHON', 'REPO_ROOT']
    ), "verify_env.sh must export REPO_ROOT, VENV_PYTHON, and PYTHON"


def test_verify_env_defines_venv_python_path():
    content = VERIFY_ENV_PATH.read_text()
    assert ".venv/bin/python3" in content, "verify_env.sh must check .venv/bin/python3"


def test_verify_env_prepends_to_path():
    content = VERIFY_ENV_PATH.read_text()
    assert "PATH=" in content, "verify_env.sh must prepend .venv/bin to PATH"


def test_verify_env_does_not_auto_install():
    content = VERIFY_ENV_PATH.read_text()
    assert "pip install" not in content, "verify_env.sh must NOT auto-install packages"


def test_verify_env_does_not_print_secrets():
    content = VERIFY_ENV_PATH.read_text()
    for secret_key in ["DISCORD_BOT_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "AUDIT_HMAC_KEY"]:
        assert f'echo "${secret_key}' not in content, (
            f"verify_env.sh must not print {secret_key}"
        )


def test_verify_env_helper_functions_present():
    content = VERIFY_ENV_PATH.read_text()
    for fn in REQUIRED_FUNCTIONS:
        assert f"{fn}()" in content, f"verify_env.sh missing function: {fn}()"


def test_setup_verification_env_exists():
    assert Path("scripts/setup_verification_env.sh").is_file()


def test_verify_environment_dependencies_exists():
    assert Path("scripts/verify_environment_dependencies.sh").is_file()


def test_run_full_regression_exists():
    assert Path("scripts/run_full_regression.sh").is_file()


def test_verify_regression_runner_hardening_exists():
    assert Path("scripts/verify_regression_runner_hardening.sh").is_file()
