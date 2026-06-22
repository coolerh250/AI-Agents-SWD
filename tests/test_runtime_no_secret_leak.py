"""Step 51.4 -- runtime baseline summary + safety fields leak no secret."""

from __future__ import annotations

import re
from pathlib import Path

from shared.sdk.runtime_baseline import (
    load_runtime_baseline_summary,
    runtime_baseline_safety_fields,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "kubernetes" / "runtime-baseline-summary.yaml"
SECRET = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|kubeconfig|"
    r"(password|secret[_-]?key|token)\s*[:=]\s*[A-Za-z0-9/+=._-]{8,})",
    re.IGNORECASE,
)


def test_summary_file_has_no_secret() -> None:
    assert not SECRET.search(SUMMARY.read_text(encoding="utf-8"))


def test_safety_fields_have_no_secret() -> None:
    f = runtime_baseline_safety_fields(load_runtime_baseline_summary(SUMMARY))
    blob = repr(f)
    assert not SECRET.search(blob)


def test_summary_has_no_rendered_manifest_dump() -> None:
    # the summary is an aggregation; it must not embed rendered k8s manifests
    text = SUMMARY.read_text(encoding="utf-8")
    assert "kind: Deployment" not in text
    assert "apiVersion: apps/v1" not in text
