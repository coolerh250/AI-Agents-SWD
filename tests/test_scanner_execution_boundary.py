"""Step 54.2 -- scanner execution boundary."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scanner-execution-boundary.yaml"


def _b() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["scannerExecution"]


def test_local_only() -> None:
    assert _b()["localOnly"] is True


def test_no_upload_network_token_path_gate() -> None:
    b = _b()
    for k in (
        "externalUploadAllowed",
        "networkAllowed",
        "tokenAllowed",
        "credentialAllowed",
        "githubWriteAllowed",
        "prCreationAllowed",
        "imagePushAllowed",
        "userProvidedPathAllowed",
        "productionGateMutationAllowed",
        "reportContainsSecretValues",
        "runtimeReportsCommitted",
    ):
        assert b[k] is False, k


def test_allowlisted_targets_and_redaction() -> None:
    b = _b()
    assert b["allowlistedTargetsOnly"] is True
    assert b["allowedTargets"]
    assert b["reportRedacted"] is True
    assert b["nonProductionReportOnly"] is True
