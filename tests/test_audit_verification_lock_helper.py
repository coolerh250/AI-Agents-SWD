"""Stage 44 -- audit verification lock helper (bash, via subprocess)."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

HELPER = "scripts/lib/audit_verification_lock.sh"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _run(script: str, tmp_path, extra_env=None):
    env = {**os.environ, "AUDIT_VERIFICATION_LOCK_FILE": str(tmp_path / "audit.lock")}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-c", f"source {HELPER}; {script}"],
        capture_output=True,
        text=True,
        env=env,
        cwd=".",
    )


def test_acquire_then_release_markers(tmp_path):
    out = _run("acquire_audit_exclusive_lock testwho; release_audit_lock testwho", tmp_path)
    assert "AUDIT_VERIFICATION_LOCK: ACQUIRED testwho" in out.stdout
    assert "AUDIT_VERIFICATION_LOCK: RELEASED testwho" in out.stdout


def test_inherited_when_runner_holds(tmp_path):
    out = _run(
        "acquire_audit_exclusive_lock child",
        tmp_path,
        extra_env={"AUDIT_VERIFICATION_LOCK_HELD_BY_RUNNER": "true"},
    )
    assert "AUDIT_VERIFICATION_LOCK: INHERITED child" in out.stdout
    # Inherited path must NOT print ACQUIRED for the real lock.
    assert "ACQUIRED child" not in out.stdout


def test_with_audit_exclusive_lock_runs_command(tmp_path):
    out = _run("with_audit_exclusive_lock who echo INNER_RAN", tmp_path)
    assert "INNER_RAN" in out.stdout
    assert "AUDIT_VERIFICATION_LOCK: ACQUIRED" in out.stdout
    assert "AUDIT_VERIFICATION_LOCK: RELEASED" in out.stdout


def test_timeout_when_already_held(tmp_path):
    # Hold the lock in a background bash that sleeps, then a second acquire with
    # a 1s timeout must report TIMEOUT. Only meaningful when flock is present
    # (the mkdir fallback also serializes). Skip if flock missing.
    if shutil.which("flock") is None:
        pytest.skip("flock not available; timeout race not deterministic")
    lock = str(tmp_path / "audit.lock")
    holder = subprocess.Popen(
        [
            "bash",
            "-c",
            f"exec 200>{lock}; flock 200; sleep 3",
        ]
    )
    try:
        import time

        time.sleep(0.5)
        out = _run(
            "acquire_audit_exclusive_lock late",
            tmp_path,
            extra_env={"AUDIT_VERIFICATION_LOCK_TIMEOUT": "1"},
        )
        assert "AUDIT_VERIFICATION_LOCK: TIMEOUT late" in out.stdout
    finally:
        holder.wait(timeout=10)


def test_helper_defines_all_functions(tmp_path):
    out = _run(
        "for f in acquire_audit_read_lock acquire_audit_exclusive_lock release_audit_lock "
        "with_audit_read_lock with_audit_exclusive_lock assert_no_audit_tamper_residue "
        "assert_audit_chain_clean_or_known_blocker record_lock_metadata "
        "fail_if_parallel_audit_mutation_detected; do "
        'type -t "$f" || echo "MISSING $f"; done',
        tmp_path,
    )
    assert "MISSING" not in out.stdout


def test_helper_does_not_echo_secrets():
    content = open(HELPER, encoding="utf-8").read()
    for key in ["AUDIT_HMAC_KEY", "DISCORD_BOT_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"]:
        assert f"echo ${key}" not in content
        assert f'echo "${key}' not in content
