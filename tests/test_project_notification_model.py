"""Step 57 -- project notification model (mock only; no external send)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NOTIFY = ROOT / "infra" / "delivery" / "project-notification-model.yaml"


def _d() -> dict:
    return (yaml.safe_load(NOTIFY.read_text(encoding="utf-8")) or {})["projectNotificationModel"]


def test_external_send_disabled() -> None:
    d = _d()
    assert d["externalSendEnabled"] is False
    assert d["productionReady"] is False
    rules = d["rules"]
    for k in ("externalSend", "slackSend", "emailSend", "webhookSend"):
        assert rules[k] is False


def test_only_mock_channel_enabled() -> None:
    ch = _d()["channels"]
    assert ch["mock_event"]["enabled"] is True
    assert ch["slack"]["enabled"] is False
    assert ch["email"]["enabled"] is False
