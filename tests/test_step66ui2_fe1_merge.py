"""Step 66UI.2-FE.1-M -- Navigation Grouping / IA Shell merge record (docs + repo-state checks).

Merge-record stage: this file itself changes no runtime code. It confirms
the merge record docs exist and state the required facts, that the
navigation grouping artifacts are now present on main with the FIX1
Delivery Package remediation intact, and that the frontend branch is now
merged into main (the expected post-merge state).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE_BRANCH_REF = "origin/frontend/66ui2-navigation-grouping"
NAV_TSX = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"

REVIEW_DOCS = {
    "merge-record": ROOT / "docs" / "frontend" / "66ui2-navigation-ia" / "merge-record.md",
    "fe1-merge-record": ROOT / "docs" / "test" / "step66ui2-fe1-merge-record.md",
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in REVIEW_DOCS.values())


def test_review_docs_exist() -> None:
    for name, p in REVIEW_DOCS.items():
        assert p.is_file(), name


def test_product_owner_authorization_recorded() -> None:
    text = _norm(_all_text())
    assert "product owner explicitly authorized merge" in text


def test_merge_source_and_target_recorded() -> None:
    text = _norm(_all_text())
    assert "frontend/66ui2-navigation-grouping" in text
    assert "merge target" in text or "merge target:" in _all_text().lower()


def test_delivery_package_conflict_closed() -> None:
    text = _norm(_all_text())
    assert "delivery package" in text
    assert "closed" in text


def test_demo_evidence_gap_accepted_non_blocking() -> None:
    text = _norm(_all_text())
    assert "demo evidence" in text
    assert "accepted" in text


def test_no_backend_api_database_workflow_change_claimed() -> None:
    text = _norm(_all_text())
    assert "backend changed: no" in text or "no backend changed" in text
    assert "api changed: no" in text or "no api changed" in text
    assert "database changed: no" in text or "no database changed" in text
    assert "workflow changed: no" in text or "no workflow changed" in text


def test_no_production_or_external_action_claimed() -> None:
    text = _norm(_all_text())
    assert "no production action" in text or "production action: no" in text
    assert "no external action" in text or "external action: no" in text


def test_post_merge_verification_documented() -> None:
    text = _norm(_all_text())
    assert "post-merge verification" in text


def test_navigation_grouping_artifacts_present_on_main() -> None:
    assert NAV_TSX.is_file()
    source = NAV_TSX.read_text(encoding="utf-8")
    for group_id in (
        '"overview"',
        '"team-work"',
        '"deliveries"',
        '"operator-center"',
        '"governance"',
        '"platform-ops"',
        '"settings"',
    ):
        assert group_id in source, group_id


def test_delivery_package_under_platform_ops_on_main() -> None:
    source = NAV_TSX.read_text(encoding="utf-8")
    deliveries_section = re.search(r'id: "deliveries".*?id: "operator-center"', source, re.DOTALL)
    assert deliveries_section is not None
    assert 'to: "/delivery-package"' not in deliveries_section.group(0)
    platform_ops_section = re.search(r'id: "platform-ops".*?id: "settings"', source, re.DOTALL)
    assert platform_ops_section is not None
    assert 'to: "/delivery-package"' in platform_ops_section.group(0)


def test_frontend_branch_now_merged_into_main() -> None:
    res = _git("cat-file", "-e", FE_BRANCH_REF)
    if res.returncode != 0:
        return  # ref not resolvable locally in this environment; nothing to assert
    merged = _git("merge-base", "--is-ancestor", FE_BRANCH_REF, "HEAD")
    assert merged.returncode == 0, "frontend branch expected to be merged into main by this stage"


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in REVIEW_DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name


def test_no_sensitive_identifiers() -> None:
    text = _all_text().lower()
    for forbidden in ("10.0.1.31", "aiagent-swd", "itadmin"):
        assert forbidden not in text


def test_marker_pass_present() -> None:
    text = REVIEW_DOCS["fe1-merge-record"].read_text(encoding="utf-8")
    assert "STEP66UI2_FE1_MERGE_VERIFY: PASS" in text
