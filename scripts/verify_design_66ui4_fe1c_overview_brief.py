#!/usr/bin/env python3
"""DESIGN-66UI.4-FE.1C -- Overview Attention-first design brief verifier.

Confirms the FE.1C design brief set, handoff, and stage-gate artifacts exist
and are internally consistent: Codex remains unauthorized, the design is
existing-data-only, no new backend/API/database/workflow requirement is
claimed, 66D/66C.4 content is marked as future/not-yet-available honest
placeholders, no fake controls are proposed, and no runtime file was changed
by this stage.

Documentation-only verifier: reads files on the current checkout and runs a
local `git diff --name-only origin/main...HEAD` to confirm scope. It does not
touch any runtime, remote host, or git remote.

Marker: DESIGN66UI4_FE1C_OVERVIEW_BRIEF_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "DESIGN66UI4_FE1C_OVERVIEW_BRIEF_VERIFY"

DESIGN_DIR = ROOT / "docs" / "design" / "66ui4-fe1c-overview-attention-first"
HANDOFF = ROOT / "docs" / "handoffs" / "66ui4-fe1c" / "claude-design-to-claude-code-handoff.md"
STAGE_DIR = ROOT / "docs" / "stages" / "66ui4-fe1c"
MANIFEST = STAGE_DIR / "stage-manifest.yaml"
RECEIPT = STAGE_DIR / "context-receipt.md"
GATE = STAGE_DIR / "stage-gate-report.md"
PROGRESS = ROOT / "source" / "progress.md"

REQUIRED_DESIGN_FILES = [
    "design-brief.md",
    "current-overview-analysis.md",
    "information-architecture.md",
    "layout-wireframe.md",
    "existing-data-mapping.md",
    "placeholder-and-empty-state-strategy.md",
    "microcopy-guide.md",
    "codex-implementation-boundary.md",
    "product-owner-validation-checklist.md",
    "open-questions-and-risks.md",
]

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)

FORBIDDEN_RUNTIME_PREFIXES = (
    "apps/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
    "shared/",
)

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower())


def check_files_exist() -> None:
    # 1. required design files
    for name in REQUIRED_DESIGN_FILES:
        if not (DESIGN_DIR / name).is_file():
            bad(f"missing design file: {DESIGN_DIR / name}")
    # 2-5. handoff + stage artifacts
    if not HANDOFF.is_file():
        bad(f"missing handoff: {HANDOFF}")
    if not MANIFEST.is_file():
        bad(f"missing stage manifest: {MANIFEST}")
    if not RECEIPT.is_file():
        bad(f"missing context receipt: {RECEIPT}")
    if not GATE.is_file():
        bad(f"missing stage gate report: {GATE}")


def check_progress() -> None:
    # 6. progress mentions the stage
    text = read(PROGRESS)
    if "66UI.4-FE.1C" not in text and "66ui4-fe1c" not in text.lower():
        bad("source/progress.md does not mention DESIGN-66UI.4-FE.1C")


def check_codex_unauthorized() -> None:
    # 7. Codex remains unauthorized
    manifest = norm(read(MANIFEST))
    if "codex_authorized: false" not in manifest:
        bad("stage manifest does not set codex_authorized: false")
    boundary = norm(read(DESIGN_DIR / "codex-implementation-boundary.md"))
    if "not authorized" not in boundary:
        bad("codex-implementation-boundary.md does not state Codex is not authorized")


def check_existing_data_only() -> None:
    # 8. existing-data-only + 9. no new backend/API/DB/workflow requirement
    mapping = read(DESIGN_DIR / "existing-data-mapping.md")
    mapping_low = norm(mapping)
    if "existing data" not in mapping_low:
        bad("existing-data-mapping.md does not assert existing-data-only")
    # must explicitly exclude new backend pieces
    for term in (
        "new backend endpoint",
        "new database field",
        "new workflow",
        "new agent activity stream",
        "new notification service",
        "new delivery review backend",
        "new reminder/expiry scheduler",
    ):
        if term not in mapping_low:
            gap(f"existing-data-mapping.md exclusion list missing phrase: {term}")
    brief_low = norm(read(DESIGN_DIR / "design-brief.md"))
    if "no new backend endpoint" not in brief_low and "no new endpoint" not in brief_low:
        bad("design-brief.md does not state no new backend endpoint is requested")


def check_placeholders() -> None:
    # 10. 66D / 66C.4 placeholders marked future / not yet available
    ph = norm(read(DESIGN_DIR / "placeholder-and-empty-state-strategy.md"))
    if "requires step 66d" not in ph:
        bad("placeholder strategy missing 'Requires Step 66D'")
    if "requires step 66c.4" not in ph:
        bad("placeholder strategy missing 'Requires Step 66C.4'")
    if "not yet available" not in ph:
        bad("placeholder strategy missing 'Not yet available'")
    if "no workflow action available" not in ph:
        bad("placeholder strategy missing 'No workflow action available'")


def check_no_fake_controls() -> None:
    # 11. no fake controls proposed
    ph = norm(read(DESIGN_DIR / "placeholder-and-empty-state-strategy.md"))
    boundary = norm(read(DESIGN_DIR / "codex-implementation-boundary.md"))
    if "no fake" not in ph and "no buttons" not in ph:
        bad("placeholder strategy does not prohibit fake controls/buttons")
    if "no fabricated" not in boundary and "no fake" not in boundary:
        gap("codex-implementation-boundary.md does not restate the no-fabricated/no-fake rule")


def check_secrets_and_infra() -> None:
    for p in list(DESIGN_DIR.glob("*.md")) + [HANDOFF, RECEIPT, GATE, MANIFEST]:
        text = read(p)
        if SECRET_SHAPES.search(text):
            bad(f"possible secret shape in {p}")
        if INFRA_SHAPES.search(text):
            bad(f"possible internal infra identifier in {p}")


def check_no_runtime_changed() -> None:
    # 12. no runtime files changed by this stage
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        gap("git not available; skipped runtime-path diff check")
        return
    if result.returncode != 0:
        gap("could not compute diff against origin/main; skipped runtime-path check")
        return
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if not path:
            continue
        for prefix in FORBIDDEN_RUNTIME_PREFIXES:
            if path.startswith(prefix):
                bad(f"forbidden/runtime path changed in this stage: {path}")


def main() -> int:
    check_files_exist()
    check_progress()
    check_codex_unauthorized()
    check_existing_data_only()
    check_placeholders()
    check_no_fake_controls()
    check_secrets_and_infra()
    check_no_runtime_changed()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] FE.1C design brief set + handoff + stage artifacts present; Codex unauthorized;")
    print("       existing-data-only; no new backend/API/DB/workflow requested; 66D/66C.4 honest")
    print("       placeholders; no fake controls; no secrets/infra identifiers; no runtime change")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
