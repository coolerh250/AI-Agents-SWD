"""Step 54.3 -- container runtime security alignment."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-runtime-security-alignment.yaml"


def _a() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["runtimeAlignment"]


def test_step51_securitycontext_mapped() -> None:
    sc = _a()["helmSecurityContextBaseline"]
    assert sc["runAsNonRoot"] is True
    assert sc["readOnlyRootFilesystem"] is True
    assert sc["allowPrivilegeEscalation"] is False


def test_dockerfile_user_gap_recorded() -> None:
    a = _a()
    assert a["imageReality"]["firstPartyImageUser"] == "root"
    assert a["imageReality"]["dockerfileNonRootComplete"] is False
    assert a["gap"]["staticContextNotEqualImageRuntimeCompatibility"] is True


def test_cluster_smoke_required_not_production() -> None:
    a = _a()
    assert a["clusterSmokeRequired"] is True
    assert a["productionReady"] is False
