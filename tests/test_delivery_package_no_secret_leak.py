"""Stage 49 -- delivery package report / sections carry no secrets."""

from __future__ import annotations

import json

from delivery_package_fakes import build_fake_package

_SECRET_MARKERS = (
    "ghp_",
    "sk-",
    "xoxb-",
    "DISCORD_BOT_TOKEN",
    "ANTHROPIC_API_KEY",
    "BEGIN PRIVATE",
)


async def test_report_and_sections_have_no_secret(tmp_path, monkeypatch) -> None:
    result, stores = await build_fake_package(tmp_path, monkeypatch)
    store = stores["package"]
    blob = json.dumps(await store.get_delivery_package_report(result.package_id))
    blob += json.dumps(await store.get_package_sections(result.package_id))
    blob += json.dumps(await store.get_handoff_summaries(result.package_id))
    for marker in _SECRET_MARKERS:
        assert marker not in blob
