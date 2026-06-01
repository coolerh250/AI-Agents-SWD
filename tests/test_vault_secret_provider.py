"""Stage 26 — VaultKvSecretProvider safe error + redaction tests.

No real Vault is contacted. Every test injects a stub HTTP getter so
the provider's HTTP behaviour is deterministic.
"""

from __future__ import annotations

from shared.sdk.secrets import REDACTION_TOKEN, SecretRef, VaultKvSecretProvider


def _ok_getter(payload):
    def _get(url, headers, timeout):
        # Vault KV v2 returns the secret data under `data.data`.
        return 200, {"data": {"data": payload}}

    return _get


def test_vault_provider_not_configured_returns_absent():
    p = VaultKvSecretProvider(addr="", token_ref=SecretRef(name="VAULT_TOKEN", present=False))
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.present is False
    status = p.status
    assert status["configured"] is False
    assert status["reachable"] is False


def test_vault_provider_reads_kv_payload():
    token = SecretRef(name="VAULT_TOKEN", _value="vault-token-only-in-memory", present=True)
    p = VaultKvSecretProvider(
        addr="http://vault:8200",
        token_ref=token,
        http_getter=_ok_getter({"GITHUB_TOKEN": "fake-gh", "POSTGRES_PASSWORD": "pw"}),
    )
    assert p.has_secret("GITHUB_TOKEN") is True
    assert p.get_secret("POSTGRES_PASSWORD").reveal() == "pw"
    # listing returns names only — no value substring
    names = p.list_available_secrets()
    assert sorted(names) == ["GITHUB_TOKEN", "POSTGRES_PASSWORD"]
    for n in names:
        assert "fake-gh" not in n


def test_vault_provider_http_error_safe():
    def _bad(url, headers, timeout):
        return 500, {"errors": ["server down"]}

    token = SecretRef(name="VAULT_TOKEN", _value="t", present=True)
    p = VaultKvSecretProvider(addr="http://vault:8200", token_ref=token, http_getter=_bad)
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.present is False
    assert "http_500" in p.status["last_error"] or p.status["last_error"]


def test_vault_provider_token_never_in_status():
    token = SecretRef(name="VAULT_TOKEN", _value="hvs.NEVER_LEAK_THIS_TOKEN", present=True)
    p = VaultKvSecretProvider(
        addr="http://vault:8200",
        token_ref=token,
        http_getter=_ok_getter({"X": "y"}),
    )
    # Trigger a load so status reflects the call.
    p.get_secret("X")
    status = p.status
    serialised = repr(status) + str(status)
    assert "hvs.NEVER_LEAK_THIS_TOKEN" not in serialised


def test_vault_provider_reload_re_reads():
    state = {"data": {"data": {"K": "v1"}}}

    def _get(url, headers, timeout):
        return 200, dict(state)

    token = SecretRef(name="VAULT_TOKEN", _value="t", present=True)
    p = VaultKvSecretProvider(addr="http://vault:8200", token_ref=token, http_getter=_get)
    assert p.get_secret("K").reveal() == "v1"
    state["data"] = {"data": {"K": "v2"}}
    # Without reload, the cached value stays.
    assert p.get_secret("K").reveal() == "v1"
    p.reload()
    assert p.get_secret("K").reveal() == "v2"


def test_vault_provider_secret_ref_renders_redacted():
    token = SecretRef(name="VAULT_TOKEN", _value="t", present=True)
    p = VaultKvSecretProvider(
        addr="http://vault:8200",
        token_ref=token,
        http_getter=_ok_getter({"GITHUB_TOKEN": "fake-gh"}),
    )
    ref = p.get_secret("GITHUB_TOKEN")
    assert REDACTION_TOKEN in repr(ref)
    assert "fake-gh" not in repr(ref)
    assert str(ref) == REDACTION_TOKEN
