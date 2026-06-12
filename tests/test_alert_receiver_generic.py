"""Stage 40 -- structural tests for the generic alert receiver."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_receiver() -> str:
    return (_REPO_ROOT / "apps" / "orchestrator" / "src" / "alert_receiver.py").read_text(
        encoding="utf-8"
    )


def test_generic_endpoint_registered():
    src = _read_receiver()
    assert '@router.post("/generic")' in src


def test_generic_validates_alert_name():
    src = _read_receiver()
    assert "alert_name is required" in src


def test_generic_calls_normalizer():
    src = _read_receiver()
    assert "normalize_generic_alert" in src


def test_health_endpoint_registered():
    src = _read_receiver()
    assert '@router.get("/health")' in src


def test_health_exposes_production_executed_false():
    src = _read_receiver()
    assert '"production_executed": False' in src


def test_health_exposes_real_escalation_disabled():
    src = _read_receiver()
    assert '"real_escalation_enabled": False' in src


def test_receiver_prefix_is_alerts():
    src = _read_receiver()
    assert 'prefix="/alerts"' in src
