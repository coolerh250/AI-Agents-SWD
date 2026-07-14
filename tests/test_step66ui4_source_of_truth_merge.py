"""Step 66UI.4-SOT-M -- Design source-of-truth merge (docs-only checks).

Merge/disposition stage: this file itself changes no runtime code. It
confirms PR #4/#5 design docs are present on main, the Hybrid decision,
Delivery Package/Platform Ops placement, PR #2-superseded, PR #1-historical,
and Codex-not-authorized statements are all recorded, and the
source-of-truth record docs exist.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PR4_DECISION_RECORD = (
    ROOT
    / "docs"
    / "design"
    / "66ui3-product-ux-visual-direction"
    / "product-owner-decision-record.md"
)
PR5_DESIGN_BRIEF = (
    ROOT / "docs" / "design" / "66ui4-phase1-product-visual-language" / "design-brief.md"
)

REVIEW_DOCS = {
    "source-of-truth-record": ROOT / "docs" / "design" / "66ui-source-of-truth-record.md",
    "merge-test-record": ROOT / "docs" / "test" / "step66ui4-source-of-truth-merge-record.md",
}

NAV_TSX = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_review_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_pr4_docs_present_on_main() -> None:
    assert PR4_DECISION_RECORD.is_file()


def test_pr5_docs_present_on_main() -> None:
    assert PR5_DESIGN_BRIEF.is_file()


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_hybrid_decision_on_main() -> None:
    text = _norm(PR4_DECISION_RECORD.read_text(encoding="utf-8"))
    assert "hybrid" in text
    assert "direction a" in text
    assert "direction b" in text


def test_delivery_package_platform_ops_on_main() -> None:
    text = _norm(PR4_DECISION_RECORD.read_text(encoding="utf-8"))
    assert "delivery package" in text
    assert "platform ops" in text


def test_pr2_superseded_recorded() -> None:
    text = _norm(_all_review_text())
    assert "pr #2" in text
    assert "supersed" in text


def test_pr1_historical_reference_recorded() -> None:
    text = _norm(_all_review_text())
    assert "pr #1" in text
    assert "historical" in text


def test_codex_not_authorized_recorded() -> None:
    text = _norm(_all_review_text())
    assert "unauthorized" in text or "not authorized" in text


def test_nav_delivery_package_under_platform_ops() -> None:
    text = NAV_TSX.read_text(encoding="utf-8")
    deliveries_idx = text.find('id: "deliveries"')
    platform_ops_idx = text.find('id: "platform-ops"')
    delivery_package_idx = text.find("/delivery-package")
    assert -1 not in (deliveries_idx, platform_ops_idx, delivery_package_idx)
    assert platform_ops_idx < delivery_package_idx


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    infra = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
    for name, p in REVIEW_DOCS.items():
        assert not infra.search(p.read_text(encoding="utf-8")), name


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["merge-test-record"].read_text(encoding="utf-8")
    assert "STEP66UI4_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS" in text


def test_verifier_marker_pass() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_step66ui4_source_of_truth_merge.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert "STEP66UI4_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS" in result.stdout
    assert result.returncode == 0
