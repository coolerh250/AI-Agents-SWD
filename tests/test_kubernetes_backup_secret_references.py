"""Step 51.2C2 -- backup uses Secret references only (no inline key)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TPL = CHART / "templates" / "backup-cronjob.yaml"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_secret_refs_structure() -> None:
    refs = _v()["batchJobs"]["backup"]["secretRefs"]
    assert "database" in refs and "encryption" in refs
    # baseline: empty NAME (falls back to existingSecret); never an inline value
    assert refs["database"]["key"] == "DATABASE_URL"
    assert refs["encryption"]["key"] == "BACKUP_ENCRYPTION_KEY"


def test_template_uses_secret_keyref() -> None:
    t = TPL.read_text(encoding="utf-8")
    assert "secretKeyRef" in t
    assert "backupEncryptionKey" in t
    # no inline encryption key value
    assert "BACKUP_ENCRYPTION_KEY: " not in t.replace("$b.secretRefs.encryption.key", "")


def test_no_inline_credentials_in_values() -> None:
    raw = (CHART / "values.yaml").read_text(encoding="utf-8")
    for needle in ("postgresql://", "BEGIN", "-----BEGIN"):
        assert needle not in raw, needle
