"""Stage 40 -- escalation dry-run: must never produce real escalation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.sdk.incidents.escalation import EscalationStore
from shared.sdk.incidents.severity import SEV1_CRITICAL, SEV2_HIGH, SEV3_MEDIUM


def _make_fake_conn(policy_row=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=policy_row)
    conn.close = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_dry_run_escalation_sev1():
    policy_row = MagicMock()
    policy_row.__getitem__ = lambda self, k: {
        "policy_id": "pid1",
        "policy_name": "SEV1_default",
        "severity": SEV1_CRITICAL,
        "enabled": True,
        "dry_run": True,
        "escalation_targets": ["oncall-primary", "eng-lead"],
        "escalation_delay_minutes": 0,
        "repeat_interval_minutes": 15,
        "created_at": None,
        "updated_at": None,
        "metadata": {},
    }[k]

    store = EscalationStore(database_url="postgresql://fake/fake")
    with patch.object(store, "_connect", return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=_make_fake_conn(policy_row)),
        __aexit__=AsyncMock(return_value=False),
        fetchrow=AsyncMock(return_value=policy_row),
        close=AsyncMock(),
    )):
        result = await store.run_dry_escalation(
            incident_id="inc-1",
            severity=SEV1_CRITICAL,
        )
    assert result["dry_run"] is True
    assert result["production_executed"] is False
    assert result["real_escalation_sent"] is False


@pytest.mark.asyncio
async def test_dry_run_no_policy_returns_not_escalated():
    store = EscalationStore(database_url="postgresql://fake/fake")
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.close = AsyncMock()
    with patch.object(store, "_connect", AsyncMock(return_value=conn)):
        result = await store.run_dry_escalation(
            incident_id="inc-2",
            severity="UNKNOWN_SEV",
        )
    assert result["escalated"] is False
    assert result["dry_run"] is True
    assert result["production_executed"] is False
    assert result["real_escalation_sent"] is False


def test_escalation_never_sends_real_message():
    """Structural: no real send function is called by escalation.py."""
    import inspect

    import shared.sdk.incidents.escalation as mod

    src = inspect.getsource(mod)
    forbidden = ("requests.post", "httpx.post", "aiohttp", "webhook", "send_message")
    for term in forbidden:
        assert term not in src, f"escalation.py must not contain '{term}'"
