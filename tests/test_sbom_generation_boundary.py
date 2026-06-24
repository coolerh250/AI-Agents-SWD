"""Step 54.3 -- SBOM generation boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-generation-boundary.yaml"


def _b() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["sbomGeneration"]


def test_local_only() -> None:
    assert _b()["localOnly"] is True


def test_no_network_upload_registry_push() -> None:
    b = _b()
    for k in (
        "externalUploadAllowed",
        "networkAllowed",
        "tokenAllowed",
        "registryLoginAllowed",
        "imagePushAllowed",
        "imagePullAllowed",
        "productionAttestationAllowed",
        "committedRuntimeReportsAllowed",
    ):
        assert b[k] is False, k


def test_production_not_ready_and_scopes() -> None:
    b = _b()
    assert b["productionReady"] is False
    assert b["allowedScopes"]
