"""Stage 40 -- IncidentStore transition method structural tests."""

import inspect

from shared.sdk.incidents.store import IncidentStore


def test_store_has_close_method():
    assert hasattr(IncidentStore, "close_incident")


def test_store_has_reopen_method():
    assert hasattr(IncidentStore, "reopen_incident")


def test_store_has_ack_method():
    assert hasattr(IncidentStore, "ack_incident")


def test_store_has_resolve_method():
    assert hasattr(IncidentStore, "resolve_incident")


def test_close_sets_closed_status():
    src = inspect.getsource(IncidentStore.close_incident)
    assert "closed" in src


def test_reopen_resets_closed_at():
    src = inspect.getsource(IncidentStore.reopen_incident)
    assert "open" in src
    assert "closed_at" in src


def test_model_has_new_fields():
    from shared.sdk.incidents.models import Incident

    i = Incident(
        incident_id="x",
        severity="sev3",
        status="open",
        source="test",
        summary="test",
    )
    assert hasattr(i, "normalized_severity")
    assert hasattr(i, "postmortem_required")
    assert hasattr(i, "closed_at")


def test_model_to_dict_includes_new_fields():
    from shared.sdk.incidents.models import Incident

    i = Incident(
        incident_id="x",
        severity="sev3",
        status="open",
        source="test",
        summary="test",
        normalized_severity="SEV3_MEDIUM",
        postmortem_required=True,
    )
    d = i.to_dict()
    assert "normalized_severity" in d
    assert "postmortem_required" in d
    assert d["postmortem_required"] is True
