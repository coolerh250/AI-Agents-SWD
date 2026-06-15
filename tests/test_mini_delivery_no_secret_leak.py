"""Stage 48 -- no secret leak in pilot report / artifacts / evidence."""

from __future__ import annotations

import json

from mini_delivery_fakes import run_fake_pilot

from shared.sdk.workspace_operator.safety import contains_secret


async def test_pilot_outputs_have_no_secrets(tmp_path, monkeypatch) -> None:
    result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    pilot_store = stores["pilot"]
    report = await pilot_store.get_pilot_report(result.pilot_id)
    qa = await pilot_store.get_qa_report(result.pilot_id)
    safety = await pilot_store.get_safety_report(result.pilot_id)
    evals = await pilot_store.list_acceptance_evaluations(result.pilot_id)
    blob = json.dumps([report, qa, safety, evals])
    assert contains_secret(blob) is False
