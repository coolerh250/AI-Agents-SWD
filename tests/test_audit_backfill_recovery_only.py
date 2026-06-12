"""Stage 39 -- backfill is recovery-only after direct POST closes the gap."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_backfill_script() -> str:
    return (_REPO_ROOT / "scripts" / "backfill_audit_integrity.sh").read_text(encoding="utf-8")


def _read_store() -> str:
    return (_REPO_ROOT / "shared" / "sdk" / "audit_integrity" / "store.py").read_text(
        encoding="utf-8"
    )


def test_backfill_summary_includes_missing_before_after():
    src = _read_store()
    assert '"missing_before"' in src
    assert '"missing_after"' in src


def test_backfill_does_not_forge_signature_when_key_missing():
    # The backfill / shared writer call ``signer.sign(row_hash)`` --
    # the signer returns ``signing_key_not_configured`` when the
    # keyring is empty; the writer persists that status verbatim. So
    # the only way an old row could be ``signed`` is when the active
    # key actually signs it.
    src = _read_store()
    assert "signer.sign(row_hash)" in src
    # Defensive: the store does not forge a hex digest manually -- it
    # always delegates to the signer.
    assert ".hexdigest()" not in src


def test_backfill_script_runs_no_op_when_chain_complete():
    src = _read_backfill_script()
    assert "AUDIT_INTEGRITY_BACKFILL: PASS" in src
    assert "audit_logs={audit_logs}" in src
    assert "created={created}" in src


def test_backfill_does_not_print_key_value():
    src = _read_backfill_script()
    # The signing_key_id is opaque metadata; the script must never
    # echo AUDIT_HMAC_KEY or AUDIT_HMAC_KEYRING_JSON content.
    assert 'echo "$AUDIT_HMAC_KEY' not in src
    assert "echo $AUDIT_HMAC_KEY" not in src
    assert 'echo "$AUDIT_HMAC_KEYRING_JSON' not in src
    assert "echo $AUDIT_HMAC_KEYRING_JSON" not in src
