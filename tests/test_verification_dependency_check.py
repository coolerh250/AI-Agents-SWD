"""Stage 41 -- verify_environment_dependencies.sh structure and logic."""

from pathlib import Path


SCRIPT_PATH = Path("scripts/verify_environment_dependencies.sh")
REQUIRED_CHECKS = [
    "asyncpg",
    "httpx",
    "pydantic",
    "redis",
    "pytest",
    "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS",
    "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: FAIL",
    "curl",
    "jq",
    "docker",
]


def test_script_exists():
    assert SCRIPT_PATH.is_file(), f"Missing: {SCRIPT_PATH}"


def test_script_sources_verify_env():
    content = SCRIPT_PATH.read_text()
    assert "verify_env.sh" in content, (
        "verify_environment_dependencies.sh must source scripts/lib/verify_env.sh"
    )


def test_script_checks_asyncpg():
    content = SCRIPT_PATH.read_text()
    assert "asyncpg" in content, "must check asyncpg importability"


def test_script_checks_required_modules():
    content = SCRIPT_PATH.read_text()
    for mod in ["httpx", "pydantic", "redis", "pytest"]:
        assert mod in content, f"must check {mod}"


def test_script_checks_shell_tools():
    content = SCRIPT_PATH.read_text()
    for tool in ["curl", "jq", "docker"]:
        assert tool in content, f"must check {tool}"


def test_script_has_pass_marker():
    content = SCRIPT_PATH.read_text()
    assert "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS" in content


def test_script_has_fail_marker():
    content = SCRIPT_PATH.read_text()
    assert "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: FAIL" in content


def test_script_does_not_auto_install():
    content = SCRIPT_PATH.read_text()
    assert "pip install" not in content, "dep check script must NOT auto-install"


def test_script_checks_caveat_closure():
    content = SCRIPT_PATH.read_text()
    assert "asyncpg caveat" in content or "HOST_DEPENDENCY_CAVEAT" in content, (
        "must check host dependency caveat closure"
    )


def test_setup_script_creates_venv():
    content = Path("scripts/setup_verification_env.sh").read_text()
    assert "venv" in content
    assert "pip install" in content
    assert "SETUP_VERIFICATION_ENV: PASS" in content


def test_setup_script_calls_dep_check():
    content = Path("scripts/setup_verification_env.sh").read_text()
    assert "verify_environment_dependencies.sh" in content
