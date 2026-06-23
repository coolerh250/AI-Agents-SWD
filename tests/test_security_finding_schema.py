"""Step 54.2 -- SecurityFinding schema (redaction + path safety + determinism)."""

from __future__ import annotations

import pytest

from shared.sdk.security_findings import SecurityFinding, make_finding_id, severity_flags


def _mk(**kw) -> SecurityFinding:
    base = dict(finding_id="x", scanner="s", category="secret", severity="critical", title="t")
    base.update(kw)
    return SecurityFinding(**base)  # type: ignore[arg-type]


def test_evidence_redacted_for_secret_shape() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    f = _mk(evidence_redacted=jwt)
    assert jwt not in (f.evidence_redacted or "")
    assert "REDACTED" in (f.evidence_redacted or "")


def test_evidence_bounded() -> None:
    f = _mk(evidence_redacted="x" * 500)
    assert len(f.evidence_redacted or "") <= 161


def test_file_path_rejects_absolute_and_traversal() -> None:
    with pytest.raises(Exception):
        _mk(file_path="/etc/passwd")
    with pytest.raises(Exception):
        _mk(file_path="../../secrets")
    assert _mk(file_path="apps/orchestrator/src/main.py").file_path


def test_finding_id_deterministic() -> None:
    a = make_finding_id("s", "secret", "r", "p", 1)
    b = make_finding_id("s", "secret", "r", "p", 1)
    c = make_finding_id("s", "secret", "r", "p", 2)
    assert a == b
    assert a != c


def test_severity_flags() -> None:
    assert severity_flags("secret", "informational") == (True, False)  # any secret blocks
    assert severity_flags("sast", "critical") == (True, False)
    assert severity_flags("sast", "high") == (True, True)
    assert severity_flags("dependency", "medium") == (False, True)
    assert severity_flags("sast", "low") == (False, False)
