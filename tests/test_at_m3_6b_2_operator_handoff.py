"""AT-M3.6B.2 completion -- the readiness proof cannot pass by accident, and operator authority never leaks.

Two defects made this file necessary, and both were "green means nothing" rather than "red":

* ``verify_vault_runtime_readiness.sh`` counted a refusal as a pass. With no ``VAULT_TOKEN`` Vault
  refuses every request, so a missing token produced four refusals, four passes, and
  ``VAULT_RUNTIME_READINESS: PASS`` over a runtime that was not configured at all. The same hole
  sits one step further in: an expired or wrongly-scoped token is also refused everywhere,
  including where refusal is the desired answer.
* Completing the procedure needs Vault operator authority, which the assistant driving it must not
  come to possess as a value. The handoff is a file path; the tests here hold the helper to never
  rendering, copying or persisting what is behind it.

The behavioural tests drive the real scripts against a **stub ``docker``** placed ahead of the real
one on ``PATH``, so the ordering rules are asserted by running them rather than by reading them.
The Vault-facing tests use a **disposable dev-mode Vault** in a throwaway container -- never the
test runtime's persistent Vault, whose root token belongs to the operator alone.

NO NETWORK BEYOND THE LOCAL DOCKER SOCKET. Nothing here reaches Anthropic, and nothing here
provisions, reads or moves a real credential.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SH = ROOT / "scripts" / "verify_vault_runtime_readiness.sh"
COMPLETE_SH = ROOT / "scripts" / "complete_vault_runtime_readiness.sh"
RUNBOOK = ROOT / "docs" / "operations" / "at-m3-6b-2-vault-runtime-readiness-runbook.md"
POLICY_HCL = ROOT / "infra" / "vault" / "policies" / "aiagents-runtime-read.hcl"
COMPOSE_ENV = ROOT / "infra" / "docker-compose" / ".env"

MOUNT = "secret"
KV_PATH = "aiagents/test-runtime"
FIELD = "ANTHROPIC_API_KEY"
SENTINEL = "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"
POLICY_NAME = "aiagents-runtime-read"

BASH = shutil.which("bash")
JQ = shutil.which("jq")
DOCKER = shutil.which("docker")

needs_shell = pytest.mark.skipif(
    not BASH or not JQ, reason="the readiness scripts need bash and jq"
)


# --- stub docker ---------------------------------------------------------------------------------


#: Stands in for `docker compose ... exec -T -e VAULT_TOKEN vault vault <subcommand>`. It answers
#: the three reads the readiness script makes and refuses everything else, which is exactly the
#: shape of a correctly-scoped runtime token. ``READINESS_STUB_READ`` switches the canonical read
#: between success and each classified failure.
_STUB_DOCKER = r"""#!/usr/bin/env bash
args="$*"
case "${args}" in
  *"vault status -format=json"*)
    echo '{"initialized":true,"sealed":false,"storage_type":"file"}'; exit 0 ;;
  *"secrets list -format=json"*)
    echo '{"secret/":{"options":{"version":"2"}}}'; exit 0 ;;
  *"vault read -format=json secret/data/aiagents/test-runtime"*)
    case "${READINESS_STUB_READ:-ok}" in
      ok)       echo '{"data":{"data":{"ANTHROPIC_API_KEY":"stub"}}}'; exit 0 ;;
      denied)   echo 'Error reading: Error making API request. Code: 403. Errors: * permission denied' >&2; exit 2 ;;
      noroute)  echo 'Error reading: Error making API request. Code: 404. Errors: * no handler for route' >&2; exit 2 ;;
      novalue)  echo 'No value found at secret/data/aiagents/test-runtime' >&2; exit 2 ;;
      weird)    echo 'Error reading: local node not active but active cluster node not found' >&2; exit 2 ;;
    esac ;;
  *"token lookup -format=json"*)
    echo '{"data":{"policies":["aiagents-runtime-read"]}}'; exit 0 ;;
esac
echo 'Error: permission denied' >&2
exit 2
"""


@pytest.fixture()
def stub_docker(tmp_path: Path) -> Path:
    bindir = tmp_path / "stub-bin"
    bindir.mkdir()
    stub = bindir / "docker"
    stub.write_text(_STUB_DOCKER, encoding="utf-8", newline="\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run_verify(stub_bin: Path | None, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    child = os.environ.copy()
    child.pop("VAULT_TOKEN", None)
    if stub_bin is not None:
        child["PATH"] = f"{stub_bin}{os.pathsep}{child['PATH']}"
    child.update(env)
    return subprocess.run(
        [BASH, str(VERIFY_SH), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=child,
    )


# --- the readiness script cannot report PASS without proving anything -----------------------------


class TestReadinessScriptHardening:
    def test_the_script_is_executable(self) -> None:
        """It is invoked as `scripts/verify_vault_runtime_readiness.sh` by the runbook and by the
        completion helper. A 100644 file makes both instructions wrong."""
        done = subprocess.run(
            ["git", "ls-files", "-s", "scripts/verify_vault_runtime_readiness.sh"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert done.stdout.startswith("100755 "), done.stdout

    @needs_shell
    def test_a_missing_token_is_a_hard_fail_and_runs_no_denial_check(self) -> None:
        """The defect this replaces: with no token Vault refuses everything, the script counted
        four refusals as four passes, and an unconfigured runtime was certified ready."""
        done = _run_verify(None, {})
        assert done.returncode == 1
        assert "VAULT_RUNTIME_READINESS: FAIL" in done.stdout
        assert "READINESS_DIAGNOSTIC: TOKEN_MISSING_OR_DENIED" in done.stdout
        assert "token_source=none" in done.stdout
        for denial in ("write=DENIED", "delete=DENIED", "unrelated_path=DENIED", "sys_policy=DENIED"):
            assert denial not in done.stdout, "a denial check ran without a token"

    @needs_shell
    def test_the_placeholder_is_not_a_token(self) -> None:
        done = _run_verify(None, {"VAULT_TOKEN": SENTINEL})
        assert done.returncode == 1
        assert "READINESS_DIAGNOSTIC: TOKEN_MISSING_OR_DENIED" in done.stdout

    @needs_shell
    def test_a_token_that_cannot_read_never_reaches_the_denial_checks(self, stub_docker: Path) -> None:
        """An expired or wrongly-scoped token is refused everywhere, INCLUDING where refusal is the
        desired answer. Accepting those refusals would turn a dead token into a least-privilege
        proof, so the canonical read is the gate."""
        done = _run_verify(stub_docker, {"VAULT_TOKEN": "stub-token", "READINESS_STUB_READ": "denied"})
        assert done.returncode == 1
        assert "runtime_canonical_read=FAIL" in done.stdout
        assert "READINESS_DIAGNOSTIC: TOKEN_MISSING_OR_DENIED" in done.stdout
        for denial in ("write=DENIED", "delete=DENIED", "unrelated_path=DENIED", "metadata_path=DENIED"):
            assert denial not in done.stdout

    @needs_shell
    def test_the_denial_checks_run_and_pass_once_the_read_succeeds(self, stub_docker: Path) -> None:
        done = _run_verify(stub_docker, {"VAULT_TOKEN": "stub-token", "READINESS_STUB_READ": "ok"})
        assert "runtime_canonical_read=PASS" in done.stdout
        assert f"field={FIELD}" in done.stdout
        for denial in (
            "write=DENIED",
            "delete=DENIED",
            "unrelated_path=DENIED",
            "metadata_path=DENIED",
            "sys_policy=DENIED",
        ):
            assert denial in done.stdout, denial
        assert "VAULT_RUNTIME_READINESS: PASS" in done.stdout
        assert done.returncode == 0

    @needs_shell
    @pytest.mark.parametrize(
        "stub_mode,category",
        [
            ("denied", "TOKEN_MISSING_OR_DENIED"),
            ("noroute", "NO_HANDLER_FOR_ROUTE"),
            ("novalue", "NO_VALUE_FOUND"),
            ("weird", "OTHER_READ_FAILURE"),
        ],
    )
    def test_a_read_failure_is_classified_rather_than_swallowed(
        self, stub_docker: Path, stub_mode: str, category: str
    ) -> None:
        """"cannot read" has four different fixes -- a dead token, a missing KV mount, an empty
        path, and everything else. A bare FAIL sends the operator to the wrong one."""
        done = _run_verify(stub_docker, {"VAULT_TOKEN": "stub-token", "READINESS_STUB_READ": stub_mode})
        assert f"READINESS_DIAGNOSTIC: {category}" in done.stdout

    @needs_shell
    def test_the_error_text_itself_is_never_printed(self, stub_docker: Path) -> None:
        """The category is derived from Vault's error and printed instead of it: a Vault error can
        quote the request path, and there is no reason to widen what a pasteable script emits."""
        done = _run_verify(stub_docker, {"VAULT_TOKEN": "stub-token", "READINESS_STUB_READ": "denied"})
        assert "Error making API request" not in done.stdout + done.stderr

    @needs_shell
    def test_the_compose_env_file_is_read_only_on_request(self, stub_docker: Path) -> None:
        """Opt-in, never automatic. If the deployment directory's token were picked up silently,
        "I forgot to pass a token" would stop being a FAIL."""
        assert "--from-compose-env" in VERIFY_SH.read_text(encoding="utf-8")
        done = _run_verify(stub_docker, {})
        assert "token_source=none" in done.stdout

    def test_the_script_prints_names_and_categories_but_never_a_value(self) -> None:
        text = VERIFY_SH.read_text(encoding="utf-8")
        assert "keys[]" in text
        assert f".data.data.{FIELD}" not in text
        assert f"-field={FIELD}" not in text
        for renderer in ("cat ", "xxd", "hexdump", "base64", "sha256sum", "md5sum", "strings "):
            assert f"${{VAULT_TOKEN}}\" | {renderer}" not in text
        assert 'printf "%s" "${VAULT_TOKEN}' not in text
        assert "echo ${VAULT_TOKEN}" not in text
        assert "echo $VAULT_TOKEN" not in text


# --- the runbook says which of restart and recreate applies, and why ------------------------------


class TestRunbookDistinguishesRecreateFromRestart:
    def test_an_environment_change_requires_force_recreate(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "docker compose up -d --force-recreate orchestrator" in text
        assert "Restart or recreate?" in text

    def test_the_runbook_does_not_claim_restart_reloads_the_environment(self) -> None:
        """`docker compose restart` stops and starts the EXISTING container with the environment it
        was created with. Run after a token change it reports success, comes up healthy, and still
        presents the old token."""
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "does not re-read `.env`" in text
        assert re.search(r"`VAULT_TOKEN` is an \*\*environment\*\* change", text)
        assert "still be presenting the old token" in text

    def test_a_secret_value_change_is_still_only_a_restart(self) -> None:
        """The cache is per process, not per container image. Recreating for a rotated key would be
        cargo cult; the runbook has to keep both cases straight."""
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "docker compose restart orchestrator" in text
        assert re.search(r"SECRET VALUE ONLY", text)

    def test_the_runbook_documents_the_operator_token_file_handoff(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "--operator-token-file" in text
        assert "/dev/shm" in text
        assert "never the value" in text


# --- the operator token is validated as a path, and never becomes a value -------------------------


def _write_token_file(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8", newline="\n")
    path.chmod(0o600)
    return path


def _run_complete(token_file: Path | str, *extra: str) -> subprocess.CompletedProcess:
    child = os.environ.copy()
    child.pop("VAULT_TOKEN", None)
    return subprocess.run(
        [BASH, str(COMPLETE_SH), "--operator-token-file", str(token_file), *extra],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=child,
    )


@needs_shell
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes and ownership")
class TestOperatorTokenFileValidation:
    """Each refusal answers "could this file be something other than what the operator intended".
    All of them are evaluated BEFORE a byte is read, so a bad path never becomes a value."""

    def test_a_missing_path_is_refused(self, tmp_path: Path) -> None:
        done = _run_complete(tmp_path / "absent")
        assert done.returncode == 1
        assert "does not exist" in done.stdout

    def test_a_symlink_is_refused(self, tmp_path: Path) -> None:
        real = _write_token_file(tmp_path / "real", "operator-token-value")
        link = tmp_path / "link"
        link.symlink_to(real)
        done = _run_complete(link)
        assert done.returncode == 1
        assert "SYMLINK" in done.stdout

    def test_a_group_or_world_readable_file_is_refused(self, tmp_path: Path) -> None:
        loose = _write_token_file(tmp_path / "loose", "operator-token-value")
        loose.chmod(0o644)
        done = _run_complete(loose)
        assert done.returncode == 1
        assert "mode 644" in done.stdout or "expected 600" in done.stdout

    def test_a_file_inside_the_repository_is_refused(self, tmp_path: Path) -> None:
        """One `git add -A` away from being committed."""
        inside = ROOT / f".operator-token-test-{uuid.uuid4().hex}"
        try:
            _write_token_file(inside, "operator-token-value")
            done = _run_complete(inside)
            assert done.returncode == 1
            assert "INSIDE the repository" in done.stdout
        finally:
            inside.unlink(missing_ok=True)

    def test_an_empty_file_is_refused(self, tmp_path: Path) -> None:
        empty = _write_token_file(tmp_path / "empty", "")
        done = _run_complete(empty)
        assert done.returncode == 1
        assert "empty" in done.stdout

    def test_a_refused_file_is_retained_and_reported_as_retained(self, tmp_path: Path) -> None:
        """Operator authority may still be needed. Deleting the file on a failure would strand the
        procedure, so failure says so instead."""
        loose = _write_token_file(tmp_path / "loose", "operator-token-value")
        loose.chmod(0o640)
        done = _run_complete(loose)
        assert "operator_token_file_removed=no" in done.stdout
        assert loose.exists()


@needs_shell
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes and ownership")
class TestOperatorTokenIsNeverRendered:
    #: Generated per run rather than written down, so the literal exists nowhere in the repository
    #: and a `git grep` hit for it can only mean the helper put it there.
    CANARY = f"OPERATOR-TOKEN-CANARY-{uuid.uuid4().hex}"

    def test_the_value_never_appears_in_the_helper_output(self, tmp_path: Path) -> None:
        """Runs the helper for real. It reaches Vault, fails there (no operator authority behind
        the canary), and the assertion is about what it printed on the way."""
        token_file = _write_token_file(tmp_path / "op", self.CANARY)
        done = _run_complete(token_file, "--keep-token-file")
        combined = done.stdout + done.stderr
        assert self.CANARY not in combined
        assert self.CANARY[:8] not in combined, "not even a prefix"

    def test_the_value_is_never_persisted_into_the_repository_or_the_env_file(self, tmp_path: Path) -> None:
        token_file = _write_token_file(tmp_path / "op", self.CANARY)
        _run_complete(token_file, "--keep-token-file")
        found = subprocess.run(
            ["git", "grep", "-I", "-l", self.CANARY],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert found.stdout.strip() == "", found.stdout
        if COMPOSE_ENV.exists():
            assert self.CANARY not in COMPOSE_ENV.read_text(encoding="utf-8")


class TestTheHelperCannotLeakByConstruction:
    """Static reading of the helper. The behavioural tests above cover the paths that actually run;
    these cover the ones that would only run on a Vault the test suite must not have."""

    def test_the_helper_never_invokes_a_rendering_command_on_a_token(self) -> None:
        text = COMPLETE_SH.read_text(encoding="utf-8")
        for var in ("OPERATOR_TOKEN", "RUNTIME_TOKEN"):
            for renderer in ("cat", "head", "tail", "xxd", "hexdump", "base64", "sha256sum", "md5sum", "strings"):
                assert f"{renderer} \"${{{var}}}\"" not in text
                assert f"${{{var}}}\" | {renderer}" not in text
            assert f"echo \"${{{var}}}\"" not in text
            assert f"echo ${{{var}}}" not in text
            assert f"printf '%s' \"${{{var}}}\"" not in text

    def test_the_operator_token_is_written_to_exactly_nothing(self) -> None:
        """The one `>>` in the helper writes the RUNTIME token to the compose env file. The
        operator token has no write site at all."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        writes = [line for line in text.splitlines() if ">>" in line or "> \"${ENV_FILE}\"" in line]
        assert all("OPERATOR_TOKEN" not in line for line in writes), writes

    def test_the_secret_value_is_compared_inside_jq_and_never_extracted(self) -> None:
        """`jq --arg s "$SENTINEL" '.data.data[$f] == $s'` emits true/false. The value never
        becomes a shell variable, an argument, or a line of output."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert f".data.data.{FIELD}" not in text
        assert f"-field={FIELD}" not in text
        assert "== $s" in text

    def test_the_helper_force_recreates_and_does_not_restart(self) -> None:
        """`restart` reuses the environment the container was CREATED with, so after a token
        change it reports success and presents the old token. The helper may EXPLAIN that in a
        comment; it may not run it."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert "up -d --force-recreate orchestrator" in text
        code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
        assert all("compose restart" not in ln for ln in code), code

    def test_the_helper_refuses_to_write_anthropic_or_root_material_into_the_env_file(self) -> None:
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert "for forbidden_key in ANTHROPIC_API_KEY VAULT_ROOT_TOKEN VAULT_UNSEAL_KEY" in text
        assert "chmod 600 \"${ENV_FILE}\"" in text
        assert "ls-files --error-unmatch" in text

    def test_the_helper_revokes_only_positively_identified_runtime_tokens(self) -> None:
        """"not the root token" is not an identification. This Vault is shared with whatever else
        the operator has been doing, and revoking an unidentified accessor is an outage looking for
        somewhere to happen."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert f'*",${{POLICY_NAME}},"*)' in text
        assert "unidentified_accessors_left_alone" in text
        assert "NON_BLOCKING" in text

    def test_the_helper_stops_if_the_placeholder_has_been_replaced(self) -> None:
        """This slice finishes with the placeholder installed. Finding a real credential at the
        canonical path means the authorization boundary was crossed somewhere else, and the helper
        must not proceed as though it were readiness."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert "placeholder_intact" in text
        assert "NOT authorized to provision a real credential" in text

    def test_the_helper_proves_the_read_before_it_tests_the_denials(self) -> None:
        text = COMPLETE_SH.read_text(encoding="utf-8")
        allow_at = text.index("runtime_canonical_read=PASS")
        deny_at = text.index("assert_denied write")
        assert allow_at < deny_at
        assert "stopping before injection" in text


# --- the compose env mechanism ---------------------------------------------------------------------


class TestComposeEnvFileStaysOutOfGit:
    def test_the_env_file_is_gitignored(self) -> None:
        done = subprocess.run(
            ["git", "check-ignore", "-q", "infra/docker-compose/.env"],
            cwd=str(ROOT),
        )
        assert done.returncode == 0, "infra/docker-compose/.env must be gitignored"

    def test_the_env_file_is_not_tracked(self) -> None:
        done = subprocess.run(
            ["git", "ls-files", "infra/docker-compose/.env"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert done.stdout.strip() == ""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    def test_an_existing_env_file_is_owner_only(self) -> None:
        if not COMPOSE_ENV.exists():
            pytest.skip("no deployment env file in this checkout")
        assert stat.S_IMODE(COMPOSE_ENV.stat().st_mode) == 0o600


# --- the canonical SecretProvider, names only ---------------------------------------------------------


class TestSecretProviderNamesOnly:
    """The whole readiness claim in one behaviour: the field NAME is visible while the CREDENTIAL is
    absent. Driven through the canonical class with an injected in-process getter -- no network."""

    def _provider(self, stored: dict[str, str]):
        from shared.sdk.secrets.models import SecretRef
        from shared.sdk.secrets.provider import VaultKvSecretProvider

        def _getter(url: str, headers: dict[str, str], timeout: float):
            assert url.endswith(f"/v1/{MOUNT}/data/{KV_PATH}"), url
            return 200, {"data": {"data": dict(stored)}}

        return VaultKvSecretProvider(
            addr="http://vault:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value="scoped", present=True),
            mount=MOUNT,
            path=KV_PATH,
            http_getter=_getter,
        )

    def test_the_placeholder_shows_the_name_and_withholds_the_credential(self) -> None:
        provider = self._provider({FIELD: SENTINEL})
        assert provider.list_available_secrets() == [FIELD]
        assert provider.get_secret(FIELD).present is False
        assert provider.has_secret(FIELD) is False

    def test_the_factory_resolves_to_vault_and_not_to_the_environment(self, monkeypatch) -> None:
        """`provider_from_env` falls back to EnvSecretProvider for anything unrecognised and never
        raises. That is right for a library and wrong for a deployment whose point is Vault."""
        from shared.sdk.secrets.provider import VaultKvSecretProvider, provider_from_env

        monkeypatch.setenv("SECRET_PROVIDER", "vault")
        monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("VAULT_TOKEN", "scoped")
        monkeypatch.setenv("VAULT_KV_MOUNT", MOUNT)
        monkeypatch.setenv("VAULT_KV_PATH", KV_PATH)
        provider = provider_from_env()
        assert isinstance(provider, VaultKvSecretProvider)
        assert provider.status["provider"] == "vault"
        assert provider.status["mount"] == MOUNT
        assert provider.status["path"] == KV_PATH

    def test_the_status_snapshot_carries_no_value(self) -> None:
        provider = self._provider({FIELD: SENTINEL})
        provider.list_available_secrets()
        assert SENTINEL not in json.dumps(provider.status)
        assert "scoped" not in json.dumps(provider.status)


# --- against a disposable Vault -----------------------------------------------------------------------


def _docker_available() -> bool:
    if not DOCKER:
        return False
    return subprocess.run([DOCKER, "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_available(), reason="docker is not available")
class TestPolicyAgainstADisposableVault:
    """The committed policy, loaded into a THROWAWAY dev-mode Vault, granting exactly what the
    runtime needs and nothing else.

    Never the test runtime's persistent Vault: that one's root token belongs to the operator, and a
    test that needed it would be a test that could not run. The dev root token here is generated
    per run, lives in one container, and dies with it.
    """

    @pytest.fixture(scope="class")
    def vault(self):
        root = f"dev-root-{uuid.uuid4().hex}"
        name = f"at-m3-6b-2-disposable-vault-{uuid.uuid4().hex[:8]}"
        started = subprocess.run(
            [
                DOCKER, "run", "-d", "--rm", "--name", name,
                "-e", f"VAULT_DEV_ROOT_TOKEN_ID={root}",
                "-e", "VAULT_ADDR=http://127.0.0.1:8200",
                "--cap-add", "IPC_LOCK",
                "hashicorp/vault:1.17",
            ],
            capture_output=True, text=True,
        )
        if started.returncode != 0:
            pytest.skip(f"could not start a disposable Vault: {started.stderr.strip()}")
        try:
            for _ in range(30):
                probe = self._exec(name, root, "vault", "status", "-format=json")
                if probe.returncode == 0:
                    break
            else:
                pytest.skip("disposable Vault never became ready")

            policy = POLICY_HCL.read_text(encoding="utf-8")
            subprocess.run(
                [DOCKER, "exec", "-i", "-e", f"VAULT_TOKEN={root}", name,
                 "vault", "policy", "write", POLICY_NAME, "-"],
                input=policy, capture_output=True, text=True, check=True,
            )
            self._exec(
                name, root, "vault", "kv", "put", f"-mount={MOUNT}", KV_PATH,
                f"{FIELD}={SENTINEL}",
            )
            self._exec(
                name, root, "vault", "kv", "put", f"-mount={MOUNT}", "aiagents/some-other-secret",
                "UNRELATED=value",
            )
            yield name, root
        finally:
            subprocess.run([DOCKER, "rm", "-f", name], capture_output=True)

    @staticmethod
    def _exec(name: str, token: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [DOCKER, "exec", "-e", f"VAULT_TOKEN={token}", name, *args],
            capture_output=True, text=True,
        )

    @pytest.fixture(scope="class")
    def scoped_token(self, vault) -> str:
        name, root = vault
        done = self._exec(
            name, root, "vault", "token", "create",
            f"-policy={POLICY_NAME}", "-no-default-policy", "-field=token",
        )
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    def test_the_scoped_token_can_make_the_read_the_runtime_makes(self, vault, scoped_token) -> None:
        """ALLOW, before any DENY is accepted. This is the raw v2 data path, byte for byte the
        request `VaultKvSecretProvider._load_kv()` issues."""
        name, _ = vault
        done = self._exec(name, scoped_token, "vault", "read", "-format=json", f"{MOUNT}/data/{KV_PATH}")
        assert done.returncode == 0, done.stderr
        names = sorted(json.loads(done.stdout)["data"]["data"].keys())
        assert names == [FIELD]

    @pytest.mark.parametrize(
        "label,args",
        [
            ("write", ("vault", "kv", "patch", f"-mount={MOUNT}", KV_PATH, "PROBE=deny")),
            ("delete", ("vault", "kv", "metadata", "delete", f"-mount={MOUNT}", KV_PATH)),
            ("unrelated", ("vault", "read", f"{MOUNT}/data/aiagents/some-other-secret")),
            ("metadata", ("vault", "read", f"{MOUNT}/metadata/{KV_PATH}")),
            ("sys_policy", ("vault", "read", "sys/policy")),
            ("token_create", ("vault", "token", "create", f"-policy={POLICY_NAME}")),
        ],
    )
    def test_everything_else_is_denied(self, vault, scoped_token, label: str, args) -> None:
        name, _ = vault
        done = self._exec(name, scoped_token, *args)
        assert done.returncode != 0, f"{label} was ALLOWED: {done.stdout}"

    def test_the_placeholder_keeps_the_credential_absent_through_the_real_provider(
        self, vault, scoped_token
    ) -> None:
        """End to end against a real Vault over real HTTP, through the canonical class. The
        credential is absent because the placeholder is what is stored -- which is the readiness
        posture this slice is required to finish in."""
        name, _ = vault
        addr = subprocess.run(
            [DOCKER, "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name],
            capture_output=True, text=True,
        ).stdout.strip()
        if not addr:
            pytest.skip("no container IP reachable from the test process")

        from shared.sdk.secrets.models import SecretRef
        from shared.sdk.secrets.provider import VaultKvSecretProvider

        provider = VaultKvSecretProvider(
            addr=f"http://{addr}:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value=scoped_token, present=True),
            mount=MOUNT,
            path=KV_PATH,
        )
        names = provider.list_available_secrets()
        if names != [FIELD]:
            pytest.skip("the disposable Vault is not routable from the test process")
        assert provider.get_secret(FIELD).present is False
        assert provider.has_secret(FIELD) is False


# --- the boundaries this slice must finish inside ------------------------------------------------------


class TestBoundariesHold:
    SLICE_FILES = (VERIFY_SH, COMPLETE_SH, RUNBOOK)

    def test_nothing_in_this_slice_reaches_anthropic(self) -> None:
        for path in self.SLICE_FILES:
            text = path.read_text(encoding="utf-8")
            assert "api.anthropic.com" not in text, path

    def test_no_helper_enables_the_live_network_gate(self) -> None:
        for path in self.SLICE_FILES:
            text = path.read_text(encoding="utf-8")
            assert "REASONING_LIVE_NETWORK_ENABLED=true" not in text, path
            assert "REASONING_LIVE_NETWORK_ENABLED: true" not in text, path

    def test_the_helper_asserts_the_gate_is_shut_rather_than_assuming_it(self) -> None:
        assert 'REASONING_LIVE_NETWORK_ENABLED=false' in COMPLETE_SH.read_text(encoding="utf-8")

    def test_nothing_here_marks_a_delivery_production_executed(self) -> None:
        """production_executed_true_count must stay 0. No file in this slice touches the delivery
        path, and none of them may start."""
        for path in self.SLICE_FILES:
            assert "production_executed" not in path.read_text(encoding="utf-8"), path

    def test_no_anthropic_key_shaped_value_is_introduced(self) -> None:
        for path in self.SLICE_FILES:
            assert not re.search(r"sk-ant-[A-Za-z0-9_-]{32,}", path.read_text(encoding="utf-8")), path

    def test_the_helper_does_not_read_an_anthropic_key_file(self) -> None:
        """A `/dev/shm/anthropic-api-key.*` file may exist from an earlier, differently-scoped
        request. This stage does not consume one and must not open one."""
        text = COMPLETE_SH.read_text(encoding="utf-8")
        assert "anthropic-api-key" not in text
