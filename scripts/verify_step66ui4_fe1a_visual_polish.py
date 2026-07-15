#!/usr/bin/env python3
"""Step 66UI.4-FE.1A visual polish verifier.

Verifies that the FE.1A stage produced the required shared artifacts, stayed
frontend-only, documented the muted-text contrast decision, and did not start
later Phase 1 work such as calm safety posture or Overview restructure.

Marker: STEP66UI4_FE1A_VISUAL_POLISH_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66UI4_FE1A_VISUAL_POLISH_VERIFY"

FILES = {
    "manifest": ROOT / "docs/stages/66ui4-fe1a/stage-manifest.yaml",
    "receipt": ROOT / "docs/stages/66ui4-fe1a/context-receipt.md",
    "gate": ROOT / "docs/stages/66ui4-fe1a/stage-gate-report.md",
    "implementation_report": ROOT
    / "docs/frontend/66ui4-phase1-product-visual-language/fe1a-visual-polish-implementation-report.md",
    "handoff": ROOT / "docs/handoffs/66ui4-fe1a/codex-to-claude-code-handoff.md",
    "test_report": ROOT / "docs/test/step66ui4-fe1a-visual-polish-test-report.md",
    "styles": ROOT / "apps/admin-console/src/styles.css",
}

ALLOWED_PREFIXES = (
    "apps/admin-console/",
    "docs/stages/66ui4-fe1a/",
    "docs/frontend/66ui4-phase1-product-visual-language/",
    "docs/handoffs/66ui4-fe1a/",
    "docs/test/",
    "source/progress.md",
    "scripts/verify_step66ui4_fe1a_visual_polish.py",
    "tests/test_step66ui4_fe1a_visual_polish.py",
)

FORBIDDEN_PREFIXES = (
    "apps/orchestrator/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
    "shared/",
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|p[@]ssw0rd|"
    r"10[.]0[.]1[.](31|32)|it[a]dmin)",
    re.IGNORECASE,
)

FORBIDDEN_CLAIMS = (
    "calm safety posture restructure implemented",
    "overview attention-first restructure implemented",
    "fe.1b implemented",
    "fe.1c implemented",
    "fe.1d implemented",
    "delivery real ui implemented",
    "reminder/expiry real ui implemented",
    "pipeline board implemented",
    "drag-and-drop implemented",
    "new agent activity model implemented",
    "fake live agent activity implemented",
    "production action performed",
    "external action performed",
    "workflow dispatch triggered",
    "workflow resume triggered",
)

failures: list[str] = []


def bad(message: str) -> None:
    failures.append(message)
    print(f"  [FAIL] {message}")


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


def git_changed_paths() -> list[str]:
    res = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        bad("git diff --name-only HEAD failed")
        return []
    return [p.replace("\\", "/") for p in res.stdout.splitlines() if p.strip()]


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        bad(f"{label} missing {needle!r}")


def main() -> int:
    texts = {name: read(path) for name, path in FILES.items()}
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    manifest = texts["manifest"]
    docs_text = "\n".join(texts.values())
    styles = texts["styles"]

    for needle in (
        'stage: "66UI.4-FE.1A"',
        'owner: "Codex"',
        'frontend_only: true',
        'backend_allowed: false',
        'api_change_allowed: false',
        'database_change_allowed: false',
        'workflow_dispatch_allowed: false',
        'workflow_resume_allowed: false',
        'production_action_allowed: false',
        'external_action_allowed: false',
        'codex_authorized: true',
        'merge_authorization_required: true',
        'deployment_authorization_required: true',
        'product_owner_validation_required: true',
    ):
        assert_contains(manifest, needle, "stage manifest")

    for needle in (
        "Visual Tokens / Typography / Card Polish",
        MARKER + ": PASS",
        "FE.1A only",
        "Muted text contrast",
        "No backend",
        "No workflow",
        "No production",
        "external",
    ):
        assert_contains(docs_text, needle, "shared artifacts")

    for needle in (
        "--surface-raised",
        "--surface-base",
        "--surface-quiet",
        "--muted-strong",
        "--focus",
        "--space-1",
        "--shadow-card",
        "focus-visible",
        ".card",
        ".badge",
        ".placeholder-panel",
        ".workroom-message",
    ):
        assert_contains(styles, needle, "styles.css")

    if "--muted: #8b949e" in styles:
        bad("muted text contrast was not increased from the old token")

    for path in git_changed_paths():
        if not any(path.startswith(prefix) or path == prefix for prefix in ALLOWED_PREFIXES):
            bad(f"changed path outside FE.1A allowed paths: {path}")
        if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            bad(f"forbidden path changed: {path}")

    low_docs = re.sub(r"\s+", " ", docs_text.lower())
    for claim in FORBIDDEN_CLAIMS:
        if claim in low_docs:
            bad(f"forbidden capability claim found: {claim}")

    if SECRET_SHAPES.search(docs_text + "\n" + styles):
        bad("secret-shaped or internal-infra content found in FE.1A authored text")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] FE.1A artifacts, visual tokens, muted-text contrast, allowed paths, "
        "and safety/scope boundaries verified"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
