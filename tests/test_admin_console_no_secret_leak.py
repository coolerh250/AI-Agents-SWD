"""Stage 50 -- admin console responses + static bundle carry no secrets / CoT."""

from __future__ import annotations

import json
from pathlib import Path

import admin_console_api
import pytest
from admin_console_helpers import wire_admin_console

_REPO = Path(__file__).resolve().parents[1]
_SECRET_MARKERS = (
    "ghp_",
    "sk-",
    "xoxb-",
    "DISCORD_BOT_TOKEN",
    "ANTHROPIC_API_KEY",
    "BEGIN PRIVATE",
)
_FORBIDDEN = ("chain_of_thought", "raw_prompt", "transcript")


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def test_responses_have_no_secret_or_cot(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    blob = json.dumps(await admin_console_api.overview())
    blob += json.dumps(await admin_console_api.projects())
    blob += json.dumps(await admin_console_api.latest_delivery_state())
    blob += json.dumps(await admin_console_api.safety_summary())
    for marker in _SECRET_MARKERS:
        assert marker not in blob
    low = blob.lower()
    for term in _FORBIDDEN:
        assert term not in low


def test_static_fallback_has_no_secret() -> None:
    html = (_REPO / "apps" / "admin-console" / "static" / "index.html").read_text(encoding="utf-8")
    for marker in _SECRET_MARKERS:
        assert marker not in html
    # The static page must implement redaction (defence in depth).
    assert "REDACTED" in html
    assert "chain_of_thought" in html  # only as a forbidden-key filter, not stored content


def test_redaction_keys_declared() -> None:
    # The frontend safety util declares the same secret-key fragments.
    safety_ts = (_REPO / "apps" / "admin-console" / "src" / "utils" / "safety.ts").read_text(
        encoding="utf-8"
    )
    for frag in ("token", "secret", "password", "api_key", "hmac", "private_key", "webhook"):
        assert frag in safety_ts
