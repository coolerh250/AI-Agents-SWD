"""Step 54.3 -- image signing / attestation model."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "image-signing-attestation-model.yaml"


def _s() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["signingAttestation"]


def test_signing_disabled_model_only() -> None:
    s = _s()
    assert s["signingConfigured"] is False
    assert s["attestationConfigured"] is False
    assert s["privateKeyCommitted"] is False
    assert s["signingPerformed"] is False
    assert s["status"] == "model_only"
    assert s["productionReady"] is False


def test_no_signing_key_committed() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()
    assert not [f for f in tracked if f.endswith((".key", ".pem")) or "cosign.key" in f.lower()]
