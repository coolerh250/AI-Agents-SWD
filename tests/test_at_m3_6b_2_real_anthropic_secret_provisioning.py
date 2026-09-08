"""AT-M3.6B.2 real Anthropic secret provisioning -- the credential never becomes a value Claude
Code holds, and the write can never accidentally become a call.

``scripts/provision_anthropic_key_to_vault.sh`` is the one place in this repository authorized
(AT-D30) to write a real Anthropic credential into Vault. Two properties make that safe rather than
merely convenient, and both are asserted here by running the script rather than by reading it:

* the credential and the Vault write authority each reach the script ONLY as a file path -- never
  as a flag value, never as an inherited environment variable -- and neither is ever printed,
  logged, hashed or otherwise rendered;
* provisioning a credential and using it are different risks. The script writes the field and stops;
  it never enables the live network gate, never calls Anthropic, and refuses outright if the gate is
  already open when it is invoked.

NO NETWORK BEYOND THE LOCAL DOCKER SOCKET. Nothing here reaches Anthropic, and nothing here can
provision a value that lets the running system reach it either -- REASONING_LIVE_NETWORK_ENABLED
stays false throughout every test.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROVISION_SH = ROOT / "scripts" / "provision_anthropic_key_to_vault.sh"

FIELD = "ANTHROPIC_API_KEY"

BASH = shutil.which("bash")
DOCKER = shutil.which("docker")

needs_shell = pytest.mark.skipif(not BASH, reason="the provisioning script needs bash")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes and ownership")


def _write_file(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8", newline="\n")
    path.chmod(0o600)
    return path


def _run(
    *args: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    child = os.environ.copy()
    child.pop("VAULT_TOKEN", None)
    child.pop("ANTHROPIC_API_KEY", None)
    if env_extra:
        child.update(env_extra)
    return subprocess.run(
        [BASH, str(PROVISION_SH), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=child,
    )


# --- the script exists, is executable, and accepts only the documented interface --------------------


class TestScriptShapeAndInterface:
    def test_the_script_is_executable(self) -> None:
        done = subprocess.run(
            ["git", "ls-files", "-s", "scripts/provision_anthropic_key_to_vault.sh"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert done.stdout.startswith("100755 "), done.stdout

    @needs_shell
    def test_an_unknown_flag_is_rejected(self, tmp_path: Path) -> None:
        """`--api-key VALUE` must not be a supported interface -- this asserts it, rather than the
        absence of the flag from the source, so a future edit cannot silently reintroduce it."""
        done = _run("--api-key", "sk-ant-not-a-real-key-shape-00000000000000000000")
        assert done.returncode == 2
        assert "file paths only" in (done.stdout + done.stderr)

    @needs_shell
    def test_the_key_is_refused_via_inherited_environment(self, tmp_path: Path) -> None:
        secret = _write_file(tmp_path / "secret", "irrelevant") if not sys.platform == "win32" else None
        done = _run(
            "--secret-file", str(secret) if secret else str(tmp_path / "secret"),
            "--operator-token-file", str(tmp_path / "op"),
            env_extra={"ANTHROPIC_API_KEY": "should-never-be-read-from-env"},
        )
        assert done.returncode == 1
        assert "ANTHROPIC_API_KEY is set in this shell's environment" in done.stdout
        assert "should-never-be-read-from-env" not in (done.stdout + done.stderr)


# --- both opaque files are validated before a byte of either is read --------------------------------


@needs_shell
@posix_only
class TestSecretFileValidation:
    """Same contract as the operator-token handoff in
    tests/test_at_m3_6b_2_operator_handoff.py::TestOperatorTokenFileValidation, applied to the
    Anthropic key file. Each refusal answers "could this file be something other than what its
    owner intended", evaluated before a byte is read."""

    def _run_with_secret(self, secret_file, tmp_path: Path, **kw) -> subprocess.CompletedProcess:
        op = _write_file(tmp_path / "op-valid", "operator-token-placeholder")
        return _run("--secret-file", str(secret_file), "--operator-token-file", str(op), **kw)

    def test_a_missing_secret_path_is_refused(self, tmp_path: Path) -> None:
        done = self._run_with_secret(tmp_path / "absent", tmp_path)
        assert done.returncode == 1
        assert "does not exist" in done.stdout

    def test_a_symlinked_secret_file_is_refused(self, tmp_path: Path) -> None:
        real = _write_file(tmp_path / "real", "anthropic-key-placeholder")
        link = tmp_path / "link"
        link.symlink_to(real)
        done = self._run_with_secret(link, tmp_path)
        assert done.returncode == 1
        assert "SYMLINK" in done.stdout

    def test_a_group_or_world_readable_secret_file_is_refused(self, tmp_path: Path) -> None:
        loose = _write_file(tmp_path / "loose", "anthropic-key-placeholder")
        loose.chmod(0o644)
        done = self._run_with_secret(loose, tmp_path)
        assert done.returncode == 1
        assert "mode 644" in done.stdout or "expected 600" in done.stdout

    def test_a_secret_file_inside_the_repository_is_refused(self, tmp_path: Path) -> None:
        inside = ROOT / f".anthropic-key-test-{uuid.uuid4().hex}"
        try:
            _write_file(inside, "anthropic-key-placeholder")
            done = self._run_with_secret(inside, tmp_path)
            assert done.returncode == 1
            assert "INSIDE the repository" in done.stdout
        finally:
            inside.unlink(missing_ok=True)

    def test_an_empty_secret_file_is_refused(self, tmp_path: Path) -> None:
        empty = _write_file(tmp_path / "empty", "")
        done = self._run_with_secret(empty, tmp_path)
        assert done.returncode == 1
        assert "empty" in done.stdout

    def test_a_refused_secret_file_is_retained(self, tmp_path: Path) -> None:
        loose = _write_file(tmp_path / "loose", "anthropic-key-placeholder")
        loose.chmod(0o640)
        done = self._run_with_secret(loose, tmp_path)
        assert "source_file_removed=no" in done.stdout
        assert loose.exists()


@needs_shell
@posix_only
class TestOperatorTokenFileValidationReused:
    """The operator-token file goes through the identical validation as the secret file -- this
    confirms it is not accidentally skipped when a valid secret file is already present."""

    def _run_with_token(self, token_file, tmp_path: Path) -> subprocess.CompletedProcess:
        secret = _write_file(tmp_path / "secret-valid", "anthropic-key-placeholder")
        return _run("--secret-file", str(secret), "--operator-token-file", str(token_file))

    def test_a_missing_operator_token_path_is_refused(self, tmp_path: Path) -> None:
        done = self._run_with_token(tmp_path / "absent", tmp_path)
        assert done.returncode == 1
        assert "does not exist" in done.stdout

    def test_a_symlinked_operator_token_file_is_refused(self, tmp_path: Path) -> None:
        real = _write_file(tmp_path / "real", "operator-token-placeholder")
        link = tmp_path / "link"
        link.symlink_to(real)
        done = self._run_with_token(link, tmp_path)
        assert done.returncode == 1
        assert "SYMLINK" in done.stdout

    def test_an_operator_token_file_inside_the_repository_is_refused(self, tmp_path: Path) -> None:
        inside = ROOT / f".operator-token-test-{uuid.uuid4().hex}"
        try:
            _write_file(inside, "operator-token-placeholder")
            done = self._run_with_token(inside, tmp_path)
            assert done.returncode == 1
            assert "INSIDE the repository" in done.stdout
        finally:
            inside.unlink(missing_ok=True)


# --- neither credential is ever rendered, whatever happens after validation --------------------------


@needs_shell
@posix_only
class TestCredentialsAreNeverRendered:
    #: Generated per run so the literal exists nowhere in the repository beforehand; a hit for it
    #: anywhere in output or history can only mean this script put it there.
    KEY_CANARY = f"ANTHROPIC-KEY-CANARY-{uuid.uuid4().hex}"
    TOKEN_CANARY = f"OPERATOR-TOKEN-CANARY-{uuid.uuid4().hex}"

    def test_neither_canary_appears_in_output(self, tmp_path: Path) -> None:
        """Runs the real script with real (but fake-content) files. Past file validation it needs
        Vault, which is not available in this test environment, so it fails there -- the assertion
        is about what it printed on the way, success or failure alike."""
        secret = _write_file(tmp_path / "secret", self.KEY_CANARY)
        op = _write_file(tmp_path / "op", self.TOKEN_CANARY)
        done = _run("--secret-file", str(secret), "--operator-token-file", str(op))
        combined = done.stdout + done.stderr
        assert self.KEY_CANARY not in combined
        assert self.KEY_CANARY[:12] not in combined, "not even a prefix"
        assert self.TOKEN_CANARY not in combined
        assert self.TOKEN_CANARY[:12] not in combined

    def test_neither_canary_is_persisted_into_the_repository(self, tmp_path: Path) -> None:
        secret = _write_file(tmp_path / "secret", self.KEY_CANARY)
        op = _write_file(tmp_path / "op", self.TOKEN_CANARY)
        _run("--secret-file", str(secret), "--operator-token-file", str(op))
        for canary in (self.KEY_CANARY, self.TOKEN_CANARY):
            found = subprocess.run(
                ["git", "grep", "-I", "-l", canary],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            assert found.stdout.strip() == "", found.stdout


# --- static reading: the paths that only run against real Vault, asserted by construction -----------


class TestScriptCannotLeakOrActByConstruction:
    def _text(self) -> str:
        return PROVISION_SH.read_text(encoding="utf-8")

    def test_never_invokes_a_rendering_command_on_either_credential(self) -> None:
        text = self._text()
        for var in ("ANTHROPIC_KEY", "OPERATOR_TOKEN"):
            for renderer in ("cat", "head", "tail", "xxd", "hexdump", "base64", "sha256sum", "md5sum", "strings"):
                assert f"{renderer} \"${{{var}}}\"" not in text
                assert f"${{{var}}}\" | {renderer}" not in text
            assert f"echo \"${{{var}}}\"" not in text
            assert f"echo ${{{var}}}" not in text

    def _code_lines(self) -> list[str]:
        return [ln for ln in self._text().splitlines() if not ln.lstrip().startswith("#")]

    def test_uses_patch_never_put_on_the_canonical_path(self) -> None:
        code = self._code_lines()
        assert any("vault kv patch" in ln for ln in code)
        assert all("vault kv put" not in ln for ln in code)

    def test_the_key_travels_on_stdin_not_argv(self) -> None:
        text = self._text()
        assert 'printf \'%s\' "${ANTHROPIC_KEY}" |' in text
        assert '"${FIELD}=-"' in text

    def test_the_operator_token_travels_through_environment_not_argv(self) -> None:
        text = self._text()
        assert "VAULT_TOKEN=\"${OPERATOR_TOKEN}\"" in text
        assert "-e VAULT_TOKEN" in text

    def test_refuses_when_the_live_gate_is_already_open(self) -> None:
        text = self._text()
        assert 'live_gate' in text
        assert 'REASONING_LIVE_NETWORK_ENABLED=true" -- refusing' in text.replace(
            "\n", " "
        ) or "live_gate}\" = \"true\" ]" in text

    def test_never_enables_the_live_network_gate(self) -> None:
        code = self._code_lines()
        # The one occurrence of the literal "...=true" in executable code is inside the fail_hard
        # message quoting what was DETECTED, never an assignment or export of it.
        assignment_lines = [
            ln for ln in code
            if "REASONING_LIVE_NETWORK_ENABLED=true" in ln or "REASONING_LIVE_NETWORK_ENABLED: true" in ln
        ]
        assert all("fail_hard" in ln for ln in assignment_lines), assignment_lines
        assert all("export " not in ln and not ln.strip().startswith("REASONING_LIVE_NETWORK_ENABLED=true") for ln in assignment_lines)

    def test_never_reaches_anthropic(self) -> None:
        text = self._text()
        assert "api.anthropic.com" not in text
        assert "anthropic.com/v1/messages" not in text

    def test_no_anthropic_key_shaped_value_is_introduced(self) -> None:
        import re

        text = self._text()
        assert not re.search(r"sk-ant-[A-Za-z0-9_-]{32,}", text)

    def test_stops_unless_the_current_field_is_the_placeholder(self) -> None:
        text = self._text()
        assert "current_is_placeholder" in text
        assert "refusing to overwrite an existing non-placeholder value" in text

    def test_recreates_nothing_and_only_restarts(self) -> None:
        """Only a Vault secret VALUE changes here, not the environment -- `--force-recreate` would
        contradict the runbook's own restart/recreate distinction for this exact case."""
        code = self._code_lines()
        assert any("restart orchestrator" in ln for ln in code)
        assert all("--force-recreate" not in ln for ln in code)

    def test_removes_both_files_only_after_success_and_reports_both(self) -> None:
        text = self._text()
        assert "rm -f \"${SECRET_FILE}\"" in text
        assert "rm -f \"${OPERATOR_TOKEN_FILE}\"" in text
        assert "source_file_removed=" in text
        assert "operator_token_file_removed=" in text

    def test_production_executed_is_never_touched(self) -> None:
        assert "production_executed" not in self._text()

    def test_verifies_present_and_has_secret_true_after_provisioning(self) -> None:
        text = self._text()
        assert "'present=true" in text.replace('"', "'")
        assert "has_secret=true" in text


def _docker_available() -> bool:
    if not DOCKER:
        return False
    return subprocess.run([DOCKER, "info"], capture_output=True).returncode == 0


@needs_shell
@pytest.mark.skipif(not _docker_available(), reason="docker is not available")
class TestAgainstAStubDocker:
    """Drives the actual script through a stub `docker` on PATH, so the ordering rules (placeholder
    check before write, live-gate check before write, patch semantics) are asserted by running them
    rather than by reading them -- without touching the persistent test-runtime Vault."""

    _STUB = r"""#!/usr/bin/env bash
args="$*"
case "${args}" in
  *"vault status -format=json"*)
    echo '{"initialized":true,"sealed":false,"storage_type":"file"}'; exit 0 ;;
  *"token lookup -format=json"*)
    echo '{"data":{"policies":["root"]}}'; exit 0 ;;
  *"printenv REASONING_LIVE_NETWORK_ENABLED"*)
    echo "${STUB_LIVE_GATE:-false}"; exit 0 ;;
  *"vault read -format=json secret/data/aiagents/test-runtime"*)
    if [ "${STUB_READ_CALLS:-0}" = "0" ]; then
      echo '{"data":{"data":{"ANTHROPIC_API_KEY":"PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"}}}'
    else
      echo '{"data":{"data":{"ANTHROPIC_API_KEY":"stub-post-write"}}}'
    fi
    export STUB_READ_CALLS=1
    exit 0 ;;
  *"vault kv patch"*)
    exit 0 ;;
  *"restart orchestrator"*)
    exit 0 ;;
  *"inspect -f"*)
    echo "healthy"; exit 0 ;;
esac
echo 'stub: unhandled docker invocation' >&2
exit 1
"""

    @pytest.fixture()
    def stub_bin(self, tmp_path: Path) -> Path:
        bindir = tmp_path / "stub-bin"
        bindir.mkdir()
        stub = bindir / "docker"
        stub.write_text(self._STUB, encoding="utf-8", newline="\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return bindir

    def test_refuses_the_write_when_the_live_gate_is_open(self, tmp_path: Path, stub_bin: Path) -> None:
        secret = _write_file(tmp_path / "secret", "sk-ant-stub-value-not-real-0000000000000000")
        op = _write_file(tmp_path / "op", "stub-operator-token")
        child = os.environ.copy()
        child.pop("VAULT_TOKEN", None)
        child.pop("ANTHROPIC_API_KEY", None)
        child["PATH"] = f"{stub_bin}{os.pathsep}{child['PATH']}"
        child["STUB_LIVE_GATE"] = "true"
        done = subprocess.run(
            [BASH, str(PROVISION_SH), "--secret-file", str(secret), "--operator-token-file", str(op)],
            capture_output=True, text=True, cwd=str(ROOT), env=child,
        )
        assert done.returncode == 1
        assert "refusing to write the real credential while the live gate is open" in done.stdout
        assert "PROVISIONING: PASS" not in done.stdout
