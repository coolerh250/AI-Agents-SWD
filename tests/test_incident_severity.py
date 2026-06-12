"""Stage 40 -- severity constant and normalization tests."""

from shared.sdk.incidents.severity import (
    SEV1_CRITICAL,
    SEV2_HIGH,
    SEV3_MEDIUM,
    SEV4_LOW,
    SEV5_INFO,
    normalize_severity_v2,
    postmortem_required,
)


def test_canonical_sev_passthrough():
    assert normalize_severity_v2("SEV1_CRITICAL") == SEV1_CRITICAL
    assert normalize_severity_v2("SEV2_HIGH") == SEV2_HIGH
    assert normalize_severity_v2("SEV3_MEDIUM") == SEV3_MEDIUM
    assert normalize_severity_v2("SEV4_LOW") == SEV4_LOW
    assert normalize_severity_v2("SEV5_INFO") == SEV5_INFO


def test_alertmanager_severity_mapping():
    assert normalize_severity_v2("critical") == SEV1_CRITICAL
    assert normalize_severity_v2("warning") == SEV3_MEDIUM
    assert normalize_severity_v2("info") == SEV5_INFO


def test_legacy_sev_mapping():
    assert normalize_severity_v2("sev1") == SEV1_CRITICAL
    assert normalize_severity_v2("sev2") == SEV2_HIGH
    assert normalize_severity_v2("sev3") == SEV3_MEDIUM
    assert normalize_severity_v2("sev4") == SEV4_LOW


def test_unknown_severity_fallback():
    assert normalize_severity_v2("unknown_garbage") == SEV4_LOW
    assert normalize_severity_v2(None) == SEV4_LOW
    assert normalize_severity_v2("") == SEV4_LOW


def test_postmortem_required_sev1_sev2():
    assert postmortem_required(SEV1_CRITICAL) is True
    assert postmortem_required(SEV2_HIGH) is True


def test_postmortem_not_required_lower_sev():
    assert postmortem_required(SEV3_MEDIUM) is False
    assert postmortem_required(SEV4_LOW) is False
    assert postmortem_required(SEV5_INFO) is False
