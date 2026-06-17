"""Step 51.2C1 -- production/staging storage fail-closed enforcement."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
VALIDATE = CHART / "templates" / "validate-values.yaml"


def _t() -> str:
    return VALIDATE.read_text(encoding="utf-8")


def test_validate_blocks_generated_pvc_in_staging_prod() -> None:
    t = _t()
    assert "must not use generatedPVC" in t


def test_validate_blocks_rwx_generated_pvc() -> None:
    assert "ReadWriteMany requires existingClaim" in _t()


def test_validate_blocks_empty_existing_claim() -> None:
    assert "existingClaim strategy requires a non-empty claim name" in _t()


def test_validate_blocks_sample_workspace_claim() -> None:
    t = _t()
    assert "$sampleClaims" in t
    assert "productionConfigured=true requires" in t


def test_prod_internal_datastores_disabled() -> None:
    for f in ("values-staging-placeholder.yaml", "values-prod-placeholder.yaml"):
        m = yaml.safe_load((CHART / f).read_text(encoding="utf-8"))
        assert m["components"]["postgres"]["enabled"] is False
        assert m["components"]["redis"]["enabled"] is False
        assert m["storage"]["workspace"]["productionConfigured"] is False
        assert m["storage"]["artifacts"]["productionConfigured"] is False


def test_validate_blocks_real_storage_class() -> None:
    assert "$badSC" in _t()
