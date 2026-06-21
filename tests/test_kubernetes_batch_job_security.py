"""Step 51.2C2 -- batch job restricted SecurityContext (helper-driven)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform" / "templates"
HELPER = TEMPLATES / "_batch_helpers.tpl"
BATCH_TEMPLATES = ["migration-job.yaml", "backup-cronjob.yaml", "restore-job.yaml"]


def test_helper_restricted_security() -> None:
    h = HELPER.read_text(encoding="utf-8")
    assert "runAsNonRoot:" in h
    assert "seccompProfile" in h
    assert "allowPrivilegeEscalation:" in h
    assert "readOnlyRootFilesystem: true" in h
    assert "drop:" in h
    assert "add:" not in h


def test_templates_use_security_helpers() -> None:
    for name in BATCH_TEMPLATES:
        t = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "aiagents.batch.podSecurityContext" in t, name
        assert "aiagents.batch.containerSecurityContext" in t, name
        assert "automountServiceAccountToken: false" in t, name


def test_templates_writable_tmp_only() -> None:
    for name in BATCH_TEMPLATES:
        t = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "mountPath: /tmp" in t, name
        assert "hostPath" not in t, name
        assert "mountPath: /app" not in t, name
