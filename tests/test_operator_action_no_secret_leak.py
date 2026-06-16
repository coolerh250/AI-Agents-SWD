"""Stage 52 -- no raw token / secret leaks through SDK outputs."""

from __future__ import annotations

import json

from shared.sdk.operator_actions.audit_events import safe_operator_action_refs
from shared.sdk.operator_actions.csrf import issue_csrf
from shared.sdk.operator_actions.session import issue_session, session_hash


def test_session_token_not_in_hash() -> None:
    tok, _i, _e = issue_session("operator-test", now=1000, env={})
    assert tok not in session_hash(tok)


def test_csrf_not_session_token() -> None:
    tok, _i, _e = issue_session("operator-test", now=1000, env={})
    c = issue_csrf(session_hash(tok), now=1000, env={})
    assert tok not in c


def test_audit_refs_carry_no_secret() -> None:
    refs = safe_operator_action_refs(
        action_type="delivery_package.accept",
        identity_key="operator-test",
        result_marker="ADMIN_CONSOLE_V0_VERIFY: PASS",
    )
    blob = json.dumps(refs).lower()
    for frag in ("password", "secret", "token=", "ghp_", "sk-", "private key"):
        assert frag not in blob
