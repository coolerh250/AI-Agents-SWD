"""Step 64E.4A -- Product UI remediation plan (planning docs + policy consistency)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

PLAN = STAGING / "product-ui-remediation-plan.md"
MAP = STAGING / "formal-admin-console-page-evidence-map.md"
REPRESENTATIVENESS = STAGING / "staging-representativeness-policy.md"
DIAGNOSTIC = STAGING / "demo-evidence-page-diagnostic-only-policy.md"
TESTQA = STAGING / "product-ui-test-qa-remediation-plan.md"
REDEPLOY = STAGING / "product-ui-staging-redeploy-plan.md"
REREVIEW = STAGING / "operator-product-ui-rereview-plan.md"
EXTERNAL = STAGING / "controlled-staging-external-integration-roadmap.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (PLAN, MAP, REPRESENTATIVENESS, DIAGNOSTIC, TESTQA, REDEPLOY, REREVIEW, EXTERNAL)

EVIDENCE_MAP = (
    ("wi-0001", "projects / work items"),
    ("agent execution", "agent executions"),
    ("workflow", "workflows / task graph"),
    ("qa/code", "qa / code"),
    ("audit", "audit / evidence"),
    ("safety", "safety center"),
)


def test_all_planning_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_formal_page_evidence_map_maps_each_type() -> None:
    lines = [ln.lower() for ln in MAP.read_text(encoding="utf-8").splitlines()]
    for evidence, page in EVIDENCE_MAP:
        assert any(evidence in ln and page in ln for ln in lines), f"{evidence} -> {page}"


def test_demo_evidence_diagnostic_only() -> None:
    low = DIAGNOSTIC.read_text(encoding="utf-8").lower()
    assert "diagnostic" in low
    assert "staging acceptance" in low
    assert "not" in low


def test_no_doc_treats_demo_evidence_as_acceptance() -> None:
    pat = re.compile(
        r"demo evidence[^.\n]{0,60}\b(is|as)\b[^.\n]{0,60}(primary )?staging acceptance",
        re.IGNORECASE,
    )
    for p in DOCS:
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            assert "not" in m.group(0).lower(), f"{p.name}: {m.group(0)[:80]}"


def test_step64e_failed_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "failed_staging_representativeness" in low or "failed_operator_validation" in low


def test_step64f_blocked_documented() -> None:
    low = "".join(p.read_text(encoding="utf-8") for p in DOCS).lower()
    assert "step 64f" in low and "block" in low


def test_subordinate_plans_defined() -> None:
    assert "64e.4b" in TESTQA.read_text(encoding="utf-8").lower()
    assert "64e.4c" in REDEPLOY.read_text(encoding="utf-8").lower()
    assert "64e.4d" in REREVIEW.read_text(encoding="utf-8").lower()


def test_external_integration_roadmap_covers_65a_to_65f() -> None:
    low = EXTERNAL.read_text(encoding="utf-8").lower()
    for step in ("65a", "65b", "65c", "65d", "65e", "65f"):
        assert step in low, step


def test_no_production_action_or_implementation_claimed() -> None:
    for p in DOCS:
        low = p.read_text(encoding="utf-8").lower()
        assert "no production action" in low, p.name
        assert "no implementation" in low, p.name
        assert "production_executed_true_count=0" in low, p.name


def test_safety_flags_present() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "production-action=false" in text
        assert "image-push=false" in text
        assert "production-action=true" not in text


def test_no_secret_values_stored() -> None:
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "p@ssw0rd" not in text
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE)


def test_step64e4a_documented_in_progress() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "64E.4A" in text
    assert "PRODUCT_UI_REMEDIATION_PLAN_VERIFY" in text
