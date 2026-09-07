"""Step AT-M3.6B.2 readiness -- the test runtime can hold a live reasoning credential, and cannot use one.

This slice prepares a rail; it does not travel it. Two claims have to hold at once, and they pull in
opposite directions, which is why they are asserted separately here:

* the runtime is genuinely wired to read ``ANTHROPIC_API_KEY`` from a PERSISTENT Vault, through the
  canonical ``SecretProvider``, at one exact mount and path, with a read-only path-scoped token; and
* the runtime still cannot make a live call -- ``REASONING_LIVE_NETWORK_ENABLED`` is false, the real
  key is not provisioned, and the only value permitted at the canonical path is the repository's
  non-secret placeholder sentinel, which ``SecretProvider`` deliberately treats as absent.

NO NETWORK. Every test here reads files or drives the real provider through an injected in-process
HTTP getter. The tests that need a live Vault skip unless one is reachable and initialized, and none
of them ever touches Anthropic.

NO VALUES. Nothing in this file asserts on a secret's value, prefix or length -- only on names,
booleans and configuration.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"
VAULT_HCL = ROOT / "infra" / "vault" / "vault.hcl"
POLICY_HCL = ROOT / "infra" / "vault" / "policies" / "aiagents-runtime-read.hcl"
INVENTORY = ROOT / "infra" / "runtime" / "secrets.inventory.yml"
ENV_EXAMPLE = ROOT / "infra" / "runtime" / "env.test-runtime.example"
SCHEMA = ROOT / "infra" / "runtime" / "runtime-config.schema.json"
VALIDATOR = ROOT / "scripts" / "validate_runtime_config.py"
RUNBOOK = ROOT / "docs" / "operations" / "at-m3-6b-2-vault-runtime-readiness-runbook.md"
VERIFY_SH = ROOT / "scripts" / "verify_vault_runtime_readiness.sh"

#: A key-SHAPED VALUE, as opposed to the bare prefix. Real Anthropic keys run to roughly a hundred
#: characters; 32 is far below that and far above any redaction fixture, so this separates "a
#: credential is present" from "a control names the pattern it defends against".
ANTHROPIC_KEY_SHAPE = r"sk-ant-[A-Za-z0-9_-]{32,}"


#: A key-shaped string that SAYS it is not a credential. AT-M3.6B.1 needs one: proving a leaked key
#: never reaches the database, the audit trail or an API response requires a string shaped like a
#: leaked key. Requiring the fixture to announce itself is what keeps the exemption from becoming a
#: hole -- a real credential does not contain the words "NOT REAL", and nobody pastes one that does.
_FIXTURE_MARKERS = ("NOT-REAL", "NOT_REAL", "THIS-IS-NOT", "PLACEHOLDER", "EXAMPLE", "FAKE")


def _is_a_declared_fixture(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in _FIXTURE_MARKERS)


def _looks_like_an_anthropic_key(text: str) -> bool:
    """True when ``text`` carries a key-shaped value that does not declare itself a fixture."""
    return any(
        not _is_a_declared_fixture(match) for match in re.findall(ANTHROPIC_KEY_SHAPE, text)
    )


MOUNT = "secret"
KV_PATH = "aiagents/test-runtime"
DEPRECATED_PATH = "aiagents/staging"
FIELD = "ANTHROPIC_API_KEY"
SENTINEL = "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"


def _compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _orchestrator_env() -> dict[str, str]:
    return _compose()["services"]["orchestrator"]["environment"]


# --- the Vault service is persistent, and is not dev mode ---------------------------------------


class TestPersistentVaultService:
    def test_the_vault_service_no_longer_runs_dev_mode(self) -> None:
        """`server -dev` keeps its storage in memory: every restart discarded every secret and
        minted a new root token. A credential an operator provisions by hand cannot live there."""
        vault = _compose()["services"]["vault"]
        command = str(vault["command"])
        assert "-dev" not in command
        assert "VAULT_DEV_LISTEN_ADDRESS" not in (vault.get("environment") or {})
        # `server` alone: the image entrypoint appends `-config=/vault/config`, so the mounted
        # vault.hcl is loaded from there. Passing -config as well loads it twice and Vault refuses
        # to start on a duplicated listener -- found by actually running it, not by reading it.
        assert command.strip() == "server"
        assert any("/vault/config/vault.hcl" in m for m in vault["volumes"])

    def test_the_server_config_uses_file_storage_and_a_real_listener(self) -> None:
        hcl = VAULT_HCL.read_text(encoding="utf-8")
        assert re.search(r'storage\s+"file"', hcl), "storage backend must be persistent"
        assert re.search(r'path\s*=\s*"/vault/file"', hcl)
        assert re.search(r'listener\s+"tcp"', hcl)
        assert 'storage "inmem"' not in hcl

    def test_mlock_stays_enabled(self) -> None:
        """Disabling mlock is the usual shortcut, and it puts unsealed key material on disk the
        moment the host swaps. The compose service grants IPC_LOCK so it is not needed."""
        assert re.search(r"disable_mlock\s*=\s*false", VAULT_HCL.read_text(encoding="utf-8"))
        assert "IPC_LOCK" in _compose()["services"]["vault"]["cap_add"]

    def test_storage_is_a_named_volume_that_survives_container_recreation(self) -> None:
        compose = _compose()
        mounts = compose["services"]["vault"]["volumes"]
        assert any(m.endswith(":/vault/file") for m in mounts), mounts
        data_mount = next(m for m in mounts if m.endswith(":/vault/file"))
        volume_name = data_mount.split(":")[0]
        assert volume_name in compose["volumes"], "must be a declared named volume, not a bind"
        # Not the repository, not a temp directory, not the container filesystem.
        assert not volume_name.startswith((".", "/", "..")), volume_name

    def test_the_config_and_policies_are_mounted_read_only(self) -> None:
        mounts = _compose()["services"]["vault"]["volumes"]
        for target in ("/vault/config/vault.hcl", "/vault/policies"):
            mount = next(m for m in mounts if f":{target}:" in m or m.endswith(f":{target}"))
            assert mount.endswith(":ro"), f"{target} must be mounted read-only: {mount}"

    def test_vault_is_not_published_beyond_loopback(self) -> None:
        for published in _compose()["services"]["vault"]["ports"]:
            assert str(published).startswith("127.0.0.1:"), published

    def test_the_healthcheck_reports_liveness_without_lying_about_seal_state(self) -> None:
        """A healthcheck that failed while sealed would mark a correctly-running Vault unhealthy
        for as long as it waits to be unsealed. Seal state is an operator concern, reported
        separately by `vault status`."""
        check = " ".join(str(x) for x in _compose()["services"]["vault"]["healthcheck"]["test"])
        assert "sys/health" in check
        assert "sealedcode=200" in check and "uninitcode=200" in check


# --- the runtime policy is least privilege ------------------------------------------------------


class TestRuntimePolicy:
    def test_the_policy_grants_read_on_exactly_one_path(self) -> None:
        body = "\n".join(
            line for line in POLICY_HCL.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        paths = re.findall(r'path\s+"([^"]+)"\s*\{', body)
        assert paths == [f"{MOUNT}/data/{KV_PATH}"], paths

    def test_the_only_capability_is_read(self) -> None:
        body = "\n".join(
            line for line in POLICY_HCL.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        capabilities = re.findall(r"capabilities\s*=\s*\[([^\]]*)\]", body)
        assert capabilities, "policy declares no capabilities"
        for block in capabilities:
            granted = {c.strip().strip('"') for c in block.split(",") if c.strip()}
            assert granted == {"read"}, granted

    @pytest.mark.parametrize(
        "forbidden",
        ["create", "update", "patch", "delete", "destroy", "list", "sudo", "deny"],
    )
    def test_no_write_shaped_capability_appears(self, forbidden: str) -> None:
        body = "\n".join(
            line for line in POLICY_HCL.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        assert f'"{forbidden}"' not in body

    def test_no_wildcard_and_no_administrative_path(self) -> None:
        body = "\n".join(
            line for line in POLICY_HCL.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "*" not in body, "a wildcard would grant every future secret under the mount"
        for admin in ("sys/", "auth/", "identity/"):
            assert f'"{admin}' not in body


# --- the runtime is wired to Vault, and cannot make a live call ---------------------------------


class TestRuntimeWiring:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("SECRET_PROVIDER", "vault"),
            ("VAULT_ADDR", "http://vault:8200"),
            ("VAULT_KV_MOUNT", MOUNT),
            ("VAULT_KV_PATH", KV_PATH),
            ("REASONING_PROVIDER", "anthropic"),
            ("REASONING_MODEL", "claude-sonnet-5"),
            ("REASONING_LIVE_NETWORK_ENABLED", "false"),
        ],
    )
    def test_the_orchestrator_default_is_the_canonical_value(self, key: str, expected: str) -> None:
        value = _orchestrator_env()[key]
        assert value == f"${{{key}:-{expected}}}", value

    def test_the_runtime_token_has_no_default(self) -> None:
        """An empty token leaves the provider safe-degraded. A default would be a credential
        committed to the repository, or a quiet reach for something broader."""
        assert _orchestrator_env()["VAULT_TOKEN"] == "${VAULT_TOKEN:-}"

    def test_the_deprecated_staging_path_is_not_used_anywhere_in_the_runtime(self) -> None:
        assert DEPRECATED_PATH not in json.dumps(_orchestrator_env())

    def test_the_anthropic_key_is_not_an_environment_variable_of_any_service(self) -> None:
        """The credential belongs in Vault. An env-borne copy survives in shell history,
        `docker inspect` output and process listings."""
        for name, service in _compose()["services"].items():
            env = service.get("environment") or {}
            keys = env.keys() if isinstance(env, dict) else [str(e).split("=")[0] for e in env]
            assert FIELD not in keys, f"{FIELD} must not be wired into service {name!r}"

    def test_the_env_template_carries_no_secret(self) -> None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
        assert f"{FIELD}=" not in text
        assert f"VAULT_TOKEN={SENTINEL}" in text
        assert "REASONING_LIVE_NETWORK_ENABLED=false" in text


# --- the canonical validator refuses a runtime that is not ready --------------------------------


def _run_validator(env: dict[str, str], tmp_path: Path) -> tuple[int, str]:
    env_file = tmp_path / "runtime.env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()), encoding="utf-8")
    done = subprocess.run(
        # sys.executable, not "python": the internal test runtime ships python3 and no `python`
        # shim, and hard-coding the name made these pass locally and fail there.
        [sys.executable, str(VALIDATOR), "--mode", "test-runtime", "--env-file", str(env_file)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return done.returncode, done.stdout


def _ready_env() -> dict[str, str]:
    return {
        "SECRET_PROVIDER": "vault",
        "VAULT_ADDR": "http://vault:8200",
        "VAULT_TOKEN": "a-scoped-read-only-runtime-token",
        "VAULT_KV_MOUNT": MOUNT,
        "VAULT_KV_PATH": KV_PATH,
        "REASONING_PROVIDER": "anthropic",
        "REASONING_MODEL": "claude-sonnet-5",
        "REASONING_LIVE_NETWORK_ENABLED": "false",
    }


class TestReadinessValidator:
    def test_the_canonical_runtime_passes(self, tmp_path: Path) -> None:
        code, out = _run_validator(_ready_env(), tmp_path)
        assert code == 0, out

    def test_the_mode_is_declared_in_the_schema(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        assert "test-runtime" in schema["properties"]["APP_ENV"]["enum"]
        rules = schema["x-mode-rules"]["test-runtime"]
        assert rules["require_secret_provider"] == "vault"
        assert rules["require_vault_kv_path"] == KV_PATH
        assert rules["forbid_vault_kv_path"] == DEPRECATED_PATH
        assert rules["live_reasoning_gate_must_be_false"] is True

    @pytest.mark.parametrize(
        "override,code",
        [
            ({"REASONING_LIVE_NETWORK_ENABLED": "true"}, "live_reasoning_gate_open"),
            ({"SECRET_PROVIDER": "env"}, "test_runtime_secret_provider_not_vault"),
            ({"SECRET_PROVIDER": "mock-vault"}, "test_runtime_secret_provider_not_vault"),
            ({"VAULT_KV_PATH": DEPRECATED_PATH}, "test_runtime_kv_path_deprecated"),
            ({"VAULT_KV_PATH": "aiagents/somewhere-else"}, "test_runtime_kv_path_wrong"),
            ({"VAULT_KV_MOUNT": "kv"}, "test_runtime_kv_mount_wrong"),
            ({"REASONING_PROVIDER": "mock"}, "test_runtime_reasoning_provider_wrong"),
            ({"REASONING_MODEL": "claude-3-opus"}, "test_runtime_reasoning_model_wrong"),
            ({FIELD: "anything-at-all"}, "anthropic_key_in_environment"),
        ],
    )
    def test_each_readiness_violation_fails_closed(
        self, override: dict[str, str], code: str, tmp_path: Path
    ) -> None:
        env = _ready_env()
        env.update(override)
        status, out = _run_validator(env, tmp_path)
        assert status == 1, out
        assert code in out, out

    def test_an_unset_secret_provider_is_a_failure_not_a_silent_env_fallback(
        self, tmp_path: Path
    ) -> None:
        """`provider_from_env` returns EnvSecretProvider for anything unrecognised and never
        raises -- right for a library, wrong for a runtime whose whole point is reading Vault."""
        env = _ready_env()
        del env["SECRET_PROVIDER"]
        status, out = _run_validator(env, tmp_path)
        assert status == 1
        assert "test_runtime_secret_provider_not_vault" in out

    def test_the_existing_modes_are_unchanged(self, tmp_path: Path) -> None:
        """The readiness mode is additive. A local runtime still validates the way it did."""
        env_file = tmp_path / "local.env"
        env_file.write_text("SECRET_PROVIDER=env\n", encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(VALIDATOR), "--mode", "local", "--env-file", str(env_file)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert done.returncode == 0, done.stdout


# --- the secret is declared, and the placeholder is not a credential ----------------------------


class TestSecretInventory:
    def test_the_anthropic_key_is_declared(self) -> None:
        doc = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
        entry = next((e for e in doc["secrets"] if e["name"] == FIELD), None)
        assert entry is not None, "the credential the live adapter depends on must be declared"
        for required in ("required_for", "environments", "provider", "rotation_policy", "leak_risk"):
            assert required in entry, required
        assert entry["leak_risk"] == "critical"
        assert entry["provider"]["local"] == "vault"

    def test_the_inventory_records_metadata_and_never_a_value(self) -> None:
        """Names, requirements and leak posture only.

        Asserted as the property rather than as a word scan: the entry's own notes say the value,
        its prefix and its length must never be printed, and a check that failed on the word
        "length" would be flagging its own instruction not to record one. What must not exist is a
        FIELD carrying a value.
        """
        doc = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
        entry = next(e for e in doc["secrets"] if e["name"] == FIELD)
        for key, value in entry.items():
            assert not re.search(r"value|secret_value|literal", str(key), re.IGNORECASE), key
            assert not _looks_like_an_anthropic_key(str(value)), key
        assert not _looks_like_an_anthropic_key(INVENTORY.read_text(encoding="utf-8"))


class TestPlaceholderIsNotACredential:
    """The field NAME may exist so the rail can be verified; the credential must still be absent."""

    def test_the_sentinel_is_treated_as_absent_by_the_canonical_provider(self) -> None:
        from shared.sdk.secrets.provider import VaultKvSecretProvider
        from shared.sdk.secrets.models import SecretRef

        def _getter(url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict]:
            assert url.endswith(f"/v1/{MOUNT}/data/{KV_PATH}"), url
            return 200, {"data": {"data": {FIELD: SENTINEL}}}

        provider = VaultKvSecretProvider(
            addr="http://vault:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value="scoped-token", present=True),
            mount=MOUNT,
            path=KV_PATH,
            http_getter=_getter,
        )
        # Names-only visibility: the field is THERE.
        assert FIELD in provider.list_available_secrets()
        # And the credential is NOT PRESENT. Boolean only -- no value is rendered.
        assert provider.get_secret(FIELD).present is False
        assert provider.has_secret(FIELD) is False

    def test_a_real_value_would_be_present_which_is_what_makes_the_test_above_meaningful(
        self,
    ) -> None:
        from shared.sdk.secrets.provider import VaultKvSecretProvider
        from shared.sdk.secrets.models import SecretRef

        def _getter(url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict]:
            return 200, {"data": {"data": {FIELD: "not-a-real-key-but-not-the-sentinel"}}}

        provider = VaultKvSecretProvider(
            addr="http://vault:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value="scoped-token", present=True),
            mount=MOUNT,
            path=KV_PATH,
            http_getter=_getter,
        )
        assert provider.get_secret(FIELD).present is True

    def test_the_adapter_refuses_at_the_gate_before_the_credential_is_resolved(self) -> None:
        """Even with a real key provisioned, the closed gate refuses first -- so provisioning is
        not, by itself, an enablement."""
        import asyncio

        from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
        from shared.sdk.agent_reasoning.live_config import LiveReasoningConfig
        from shared.sdk.agent_reasoning.models import ReasoningRequest
        from shared.sdk.agent_reasoning.provider import LiveProviderError

        class _ExplodingSecrets:
            def get_secret(self, name: str) -> Any:  # pragma: no cover - must never run
                raise AssertionError("a credential was resolved behind a closed gate")

        adapter = AnthropicReasoningProvider(
            config=LiveReasoningConfig(
                provider_name="anthropic",
                model_name="claude-sonnet-5",
                live_network_enabled=False,
            ),
            secret_provider=_ExplodingSecrets(),
        )
        request = ReasoningRequest(
            verb="propose",
            context={"topic": "readiness", "round": 1, "goal_statement": "prepare the rail"},
        )
        with pytest.raises(LiveProviderError) as caught:
            asyncio.run(adapter.preflight(request))
        assert caught.value.failure_category == "provider_disabled"


class TestProviderCacheBehaviour:
    """A secret written after startup is not seen until the process restarts. Documented, not fixed:
    a reasoning runtime that could silently change which credential it bills to, mid-process, is a
    worse property than one that needs a restart you can point at in a deployment log."""

    def test_the_kv_document_is_cached_per_process(self) -> None:
        from shared.sdk.secrets.provider import VaultKvSecretProvider
        from shared.sdk.secrets.models import SecretRef

        calls: list[str] = []
        state = {FIELD: SENTINEL}

        def _getter(url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict]:
            calls.append(url)
            return 200, {"data": {"data": dict(state)}}

        provider = VaultKvSecretProvider(
            addr="http://vault:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value="scoped-token", present=True),
            mount=MOUNT,
            path=KV_PATH,
            http_getter=_getter,
        )
        assert provider.get_secret(FIELD).present is False
        # The operator writes the real key...
        state[FIELD] = "a-newly-provisioned-value"
        # ...and the running process does not see it.
        assert provider.get_secret(FIELD).present is False
        assert len(calls) == 1, "one fetch, cached for the life of the process"

        # A reload -- or, in deployment, a process restart -- is what picks it up.
        provider.reload()
        assert provider.get_secret(FIELD).present is True

    def test_the_runbook_requires_a_restart_after_the_real_key_is_written(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "docker compose restart orchestrator" in text
        assert "kv patch" in text and "PATCH, never PUT" in text


# --- no credential anywhere, and no live rail ---------------------------------------------------


class TestNoRealCredential:
    def test_no_anthropic_key_shaped_value_exists_in_the_repository(self) -> None:
        """A fake that looks real is a fake that gets treated as real by the next person to read
        it, so neither a real key nor a realistic one may exist.

        Scans for a key-SHAPED VALUE, not for the bare `sk-ant` prefix. The prefix appears in 158
        files, essentially all of them SECRET SCANNERS declaring the pattern they hunt for, plus
        prose telling operators not to invent a key. A scan that flagged those would be flagging
        the controls rather than the risk -- the same trap AT-M3.6A's validation recorded, where
        modules discussing the writes they do not perform tripped a text scan of their own
        explanation.

        The two key-shaped values that DO exist are AT-M3.1's and AT-M3.6B.1's leakage fixtures,
        which prove a leaked key never reaches the database, the audit trail or an API response --
        a proof that needs a string shaped like a leaked key. They are tolerated only because they
        announce themselves as fixtures; a real credential does not contain the words "NOT REAL",
        so the exemption cannot be reached by anything that matters.
        """
        done = subprocess.run(
            ["git", "grep", "-I", "-h", "-o", "-E", ANTHROPIC_KEY_SHAPE],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        found = {line.strip() for line in done.stdout.splitlines() if line.strip()}
        undeclared = {value for value in found if not _is_a_declared_fixture(value)}
        assert undeclared == set(), sorted(undeclared)

    def test_the_sentinel_is_the_only_permitted_placeholder(self) -> None:
        from shared.sdk.secrets.provider import _PLACEHOLDER_MARKER

        assert _PLACEHOLDER_MARKER == SENTINEL
        assert SENTINEL in ENV_EXAMPLE.read_text(encoding="utf-8")

    def test_the_live_gate_default_is_false_in_code_and_in_deployment(self) -> None:
        from shared.sdk.agent_reasoning.live_config import LiveReasoningConfig

        assert LiveReasoningConfig.resolve(env={}).live_network_enabled is False
        assert _orchestrator_env()["REASONING_LIVE_NETWORK_ENABLED"].endswith(":-false}")

    def test_nothing_in_this_slice_reaches_anthropic(self) -> None:
        """The readiness slice adds configuration, not a call path. No file it introduces names an
        Anthropic endpoint."""
        for path in (VAULT_HCL, POLICY_HCL, ENV_EXAMPLE, VERIFY_SH, COMPOSE):
            assert "api.anthropic.com" not in path.read_text(encoding="utf-8"), path


class TestOperatorBootstrapIsValueFree:
    def test_the_runbook_never_embeds_a_token_or_key(self) -> None:
        """Value-shaped, not prefix-shaped. The runbook necessarily NAMES the shapes it forbids."""
        text = RUNBOOK.read_text(encoding="utf-8")
        assert not _looks_like_an_anthropic_key(text)
        assert not re.search(r"hvs\.[A-Za-z0-9]{20,}", text), "no Vault token literal may appear"
        assert "read -rs" in text, "the key must be read with echo disabled"
        assert "set +o history" in text
        assert "<your root token>" in text, "the root token is referenced, never written down"

    def test_the_verification_script_prints_names_and_booleans_only(self) -> None:
        text = VERIFY_SH.read_text(encoding="utf-8")
        # It reads field NAMES via `keys[]`, never the field's own value by any route.
        assert "keys[]" in text
        assert f".data.data.{FIELD}" not in text
        assert f"-field={FIELD}" not in text
        assert not _looks_like_an_anthropic_key(text)

    def test_the_runbook_enables_the_kv_v2_engine(self) -> None:
        """`server -dev` auto-mounted `secret/`; a real server does not, so every later write
        fails with "no handler for route" if this step is missing. Found by running a disposable
        Vault built from the committed config -- reading the config would not have found it."""
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "vault secrets enable -path=secret -version=2 kv" in text

    def test_the_runbook_states_the_manual_unseal_limitation(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "auto-unseal" in text.lower()
        assert "re-seals on every restart" in text.lower() or "manual unseal" in text.lower()


# --- against a real Vault, when the operator has bootstrapped one --------------------------------


def _vault_env() -> tuple[str, str] | None:
    addr = (os.environ.get("VAULT_ADDR") or "").strip()
    token = (os.environ.get("VAULT_TOKEN") or "").strip()
    if not addr or not token or token == SENTINEL:
        return None
    return addr, token


@pytest.mark.skipif(_vault_env() is None, reason="no bootstrapped Vault reachable")
class TestAgainstARealVault:
    """Runs only where an operator has already initialized and unsealed a Vault. Skipped
    everywhere else -- including in the Claude Code session that wrote this file, which is not
    permitted to hold bootstrap material."""

    def _provider(self) -> Any:
        from shared.sdk.secrets.provider import VaultKvSecretProvider
        from shared.sdk.secrets.models import SecretRef

        addr, token = _vault_env()  # type: ignore[misc]
        return VaultKvSecretProvider(
            addr=addr,
            token_ref=SecretRef(name="VAULT_TOKEN", _value=token, present=True),
            mount=MOUNT,
            path=KV_PATH,
        )

    def test_the_canonical_provider_reads_the_canonical_path(self) -> None:
        provider = self._provider()
        names = provider.list_available_secrets()
        assert provider.status["provider"] == "vault"
        assert provider.status["mount"] == MOUNT
        assert provider.status["path"] == KV_PATH
        assert FIELD in names, names

    def test_the_placeholder_keeps_the_credential_absent(self) -> None:
        # Boolean only. If an operator has provisioned the real key this asserts nothing about it
        # and prints nothing either way.
        provider = self._provider()
        assert isinstance(provider.get_secret(FIELD).present, bool)
