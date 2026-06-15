"""Stage 48 -- the pilot never writes GitHub / creates a PR."""

from __future__ import annotations

from mini_delivery_fakes import run_fake_pilot


async def test_no_github_write_or_pr(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    assert result.github_write_performed is False
    assert result.pr_created is False
    safety = await stores["pilot"].get_safety_report(result.pilot_id)
    assert safety["github_write_performed"] is False
    assert safety["pr_created"] is False
    # pilot record carries controlled-only flags
    pilot = await stores["pilot"].get_pilot(result.pilot_id)
    assert pilot["controlled_only"] is True
    assert pilot["production_executed"] is False
