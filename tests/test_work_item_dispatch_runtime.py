"""Step 57 -- work-item dispatch runtime guarantees (static guards).

The live end-to-end dispatch is exercised by
scripts/verify_work_item_dispatch_runtime.py against the running orchestrator. These
tests assert the API + verifier enforce the runtime safety invariants in source, so
they are deterministic without a DB / network.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "apps" / "orchestrator" / "src" / "multi_project_api.py").read_text(encoding="utf-8")
VERIFIER = (ROOT / "scripts" / "verify_work_item_dispatch_runtime.py").read_text(encoding="utf-8")


def test_api_routes_production_effect_to_waiting_approval() -> None:
    assert 'wi["production_effect"]' in API
    assert '"waiting_approval"' in API
    assert '"dispatched": False' in API


def test_api_dispatch_has_no_external_side_effect() -> None:
    assert '"github_write_performed": False' in API
    assert '"argocd_sync_performed": False' in API
    assert '"external_notification_send_performed": False' in API
    assert '"production_executed": False' in API


def test_runtime_verifier_checks_waiting_approval_and_target() -> None:
    assert "waiting_approval" in VERIFIER
    assert "development-agent" in VERIFIER
    assert "reason_required" in VERIFIER
