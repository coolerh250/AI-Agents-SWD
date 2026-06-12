"""Stage 40 -- lifecycle event type constants test."""

from shared.sdk.incidents.lifecycle import (
    ALL_LIFECYCLE_EVENTS,
    EVENT_INCIDENT_ACKNOWLEDGED,
    EVENT_INCIDENT_CLOSED,
    EVENT_INCIDENT_CREATED,
    EVENT_INCIDENT_ESCALATED,
    EVENT_INCIDENT_LINKED_TO_ALERT,
    EVENT_INCIDENT_POSTMORTEM_COMPLETED,
    EVENT_INCIDENT_POSTMORTEM_REQUIRED,
    EVENT_INCIDENT_REOPENED,
    EVENT_INCIDENT_RESOLVED,
    EVENT_INCIDENT_RUNBOOK_ATTACHED,
)


def test_all_lifecycle_event_types_defined():
    expected = {
        EVENT_INCIDENT_CREATED,
        EVENT_INCIDENT_ACKNOWLEDGED,
        EVENT_INCIDENT_ESCALATED,
        EVENT_INCIDENT_RESOLVED,
        EVENT_INCIDENT_CLOSED,
        EVENT_INCIDENT_REOPENED,
        EVENT_INCIDENT_POSTMORTEM_REQUIRED,
        EVENT_INCIDENT_POSTMORTEM_COMPLETED,
        EVENT_INCIDENT_LINKED_TO_ALERT,
        EVENT_INCIDENT_RUNBOOK_ATTACHED,
    }
    assert set(ALL_LIFECYCLE_EVENTS) == expected


def test_lifecycle_event_type_strings():
    assert EVENT_INCIDENT_CREATED == "incident_created"
    assert EVENT_INCIDENT_ACKNOWLEDGED == "incident_acknowledged"
    assert EVENT_INCIDENT_RESOLVED == "incident_resolved"
    assert EVENT_INCIDENT_CLOSED == "incident_closed"
    assert EVENT_INCIDENT_REOPENED == "incident_reopened"
    assert EVENT_INCIDENT_POSTMORTEM_REQUIRED == "incident_postmortem_required"
    assert EVENT_INCIDENT_LINKED_TO_ALERT == "incident_linked_to_alert"
