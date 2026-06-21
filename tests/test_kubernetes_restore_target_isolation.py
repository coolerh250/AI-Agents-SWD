"""Step 51.2C2 -- restore target isolation (fixed prefix, source != target)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"
TPL = CHART / "templates" / "restore-job.yaml"
WRAPPER = ROOT / "scripts" / "k8s_restore_drill.py"
PREFIX = "aiagents_restore_drill_"


def _v() -> dict:
    return yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))


def test_target_prefix_fixed() -> None:
    assert _v()["batchJobs"]["restore"]["targetPrefix"] == PREFIX


def test_template_target_uses_prefix_and_source_differs() -> None:
    t = TPL.read_text(encoding="utf-8")
    assert 'printf "%sscaffold" $r.targetPrefix' in t
    assert "RESTORE_SOURCE_DATABASE" in t
    assert 'value: "aiagents"' in t


def test_separate_source_target_secret_refs() -> None:
    refs = _v()["batchJobs"]["restore"]["secretRefs"]
    assert {"source", "target", "encryption"} <= set(refs)
    t = TPL.read_text(encoding="utf-8")
    assert "$srcSecret" in t and "$tgtSecret" in t


def test_wrapper_reuses_isolation_guard() -> None:
    src = WRAPPER.read_text(encoding="utf-8")
    assert "assert_isolated_restore_db" in src
    assert "DEFAULT_RESTORE_DB_PREFIX" in src


def test_validate_enforces_prefix() -> None:
    raw = (CHART / "templates" / "validate-values.yaml").read_text(encoding="utf-8")
    assert "restore.targetPrefix must be aiagents_restore_drill_" in raw
