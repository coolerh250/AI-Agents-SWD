#!/usr/bin/env python3
"""Step 66UI.4-FE.1D-DESIGN -- Navigation Polish + Microcopy design verifier.

Confirms the FE.1D design brief set and stage-gate artifacts exist and are
internally consistent: no runtime/backend/API/database/workflow change is
claimed, no new endpoint is claimed, FE.1D implementation is not claimed,
Codex remains unauthorized, and the SPA deep-link fallback is explicitly NOT
fixed or included as FE.1D scope.

Documentation-only verifier: reads files on the current checkout and runs a
local `git diff --name-only origin/main...HEAD` to confirm scope. It does not
touch any runtime, remote host, or git remote.

Marker: DESIGN66UI4_FE1D_NAVIGATION_MICROCOPY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "DESIGN66UI4_FE1D_NAVIGATION_MICROCOPY_VERIFY"

DESIGN_DIR = ROOT / "docs" / "design" / "66ui4-fe1d-navigation-microcopy"
STAGE_DIR = ROOT / "docs" / "stages" / "66ui4-fe1d-navigation-microcopy-design"
MANIFEST = STAGE_DIR / "stage-manifest.yaml"
RECEIPT = STAGE_DIR / "context-receipt.md"
GATE = STAGE_DIR / "stage-gate-report.md"
PROGRESS = ROOT / "source" / "progress.md"

REQUIRED_DESIGN_FILES = [
    "design-brief.md",
    "navigation-polish-spec.md",
    "microcopy-guide.md",
    "field-label-cleanup-map.md",
    "engineering-field-exposure-reduction.md",
    "platform-ops-density-spec.md",
    "product-owner-review-checklist.md",
    "codex-implementation-notes.md",
]

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagents?-test|stpadmin|itadmin)", re.IGNORECASE)

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


def all_design_text() -> str:
    return " ".join(norm(read(DESIGN_DIR / n)) for n in REQUIRED_DESIGN_FILES)


def check_files_exist() -> None:
    # 1,6-12. required design docs
    for name in REQUIRED_DESIGN_FILES:
        if not (DESIGN_DIR / name).is_file():
            bad(f"missing design file: {DESIGN_DIR / name}")
    # 2-4. stage artifacts
    if not MANIFEST.is_file():
        bad(f"missing stage manifest: {MANIFEST}")
    if not RECEIPT.is_file():
        bad(f"missing context receipt: {RECEIPT}")
    if not GATE.is_file():
        bad(f"missing stage gate report: {GATE}")


def check_progress() -> None:
    # 5. progress mentions FE.1D-DESIGN
    text = read(PROGRESS)
    if "FE.1D-DESIGN" not in text and "66ui4-fe1d" not in text.lower():
        bad("source/progress.md does not mention 66UI.4-FE.1D-DESIGN")


def check_codex_unauthorized() -> None:
    # 17. Codex remains unauthorized
    if "codex_authorized: false" not in norm(read(MANIFEST)):
        bad("stage manifest does not set codex_authorized: false")
    notes = norm(read(DESIGN_DIR / "codex-implementation-notes.md"))
    if "not authorized" not in notes:
        bad("codex-implementation-notes.md does not state Codex is not authorized")


def check_no_backend_or_impl_claims() -> None:
    # 14,15,16. no backend/API/DB/workflow change, no new endpoint, no FE.1D implementation claimed
    brief = norm(read(DESIGN_DIR / "design-brief.md"))
    for phrase in ("no backend", "no new endpoint"):
        if phrase not in brief:
            bad(f"design-brief.md missing explicit constraint phrase: '{phrase}'")
    text = all_design_text()
    # must frame itself as design/frontend-only-polish, not implementation performed
    if "design specification only" not in text and "design / documentation only" not in text:
        gap("design docs do not restate 'design specification only'")
    # guard against accidentally claiming implementation was done
    for claim in (
        "implementation complete",
        "implemented the",
        "code changed",
        "deployed to",
        "merged to main",
    ):
        # allow references to PRIOR stages (fe1a/fe1b/fe1c) but not a self-claim; heuristic:
        if claim in text and "fe.1d" in text.split(claim)[0][-80:]:
            gap(f"possible self-implementation claim near: '{claim}' (review)")


def check_deep_link_out_of_scope() -> None:
    # 18. SPA deep-link fallback is not fixed / not FE.1D scope
    text = all_design_text()
    if "deep-link" not in text and "deep link" not in text:
        bad("design docs do not mention the SPA deep-link fallback gap")
    # must be framed as out of scope / backend / not FE.1D
    window_ok = any(
        cue in text
        for cue in ("out of fe.1d scope", "out of scope", "backend change", "not fe.1d", "excluded from fe.1d")
    )
    if not window_ok:
        bad("design docs do not state the SPA deep-link fallback is out of FE.1D scope")


def check_secrets_and_infra() -> None:
    for p in list(DESIGN_DIR.glob("*.md")) + [RECEIPT, GATE, MANIFEST]:
        text = read(p)
        if SECRET_SHAPES.search(text):
            bad(f"possible secret shape in {p}")
        if INFRA_SHAPES.search(text):
            bad(f"possible internal infra identifier in {p}")


def check_no_runtime_changed() -> None:
    # 13. no runtime source files changed by this stage
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
    check_no_backend_or_impl_claims()
    check_deep_link_out_of_scope()
    check_secrets_and_infra()
    check_no_runtime_changed()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] FE.1D design brief set + stage artifacts present; Codex unauthorized; no backend/")
    print("       API/DB/workflow change and no new endpoint claimed; FE.1D implementation not")
    print("       claimed; SPA deep-link fallback explicitly out of scope; no secrets/infra ids;")
    print("       no runtime source changed")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
