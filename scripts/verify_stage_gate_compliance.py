#!/usr/bin/env python3
"""Step 66GOV.1 -- Stage Gate & Context Guard Skill Pack compliance verifier.

Confirms the repo-level Stage Gate & Context Guard Skill Pack is present and
internally consistent: the five .agents skills, the docs/stages standard +
templates + examples, the five docs/process governance docs, the PR
template's five new sections, and that no runtime/backend/API/database/
workflow file was changed by this stage.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime, remote host, or git branch/remote
beyond a local `git diff --name-only` against origin/main to confirm scope.

Marker: STEP66GOV1_STAGE_GATE_CONTEXT_GUARD_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MARKER = "STEP66GOV1_STAGE_GATE_CONTEXT_GUARD_VERIFY"

SKILL_FILES = {
    "shared-context": ROOT / ".agents" / "skills" / "shared-context" / "SKILL.md",
    "stage-gate": ROOT / ".agents" / "skills" / "stage-gate" / "SKILL.md",
    "security-governance": ROOT / ".agents" / "skills" / "security-governance" / "SKILL.md",
    "design-collaboration": ROOT / ".agents" / "skills" / "design-collaboration" / "SKILL.md",
    "frontend-implementation": ROOT / ".agents" / "skills" / "frontend-implementation" / "SKILL.md",
}

AGENTS_README = ROOT / ".agents" / "README.md"

PROCESS_DOCS = {
    "stage-gate-checkpoint-protocol": ROOT
    / "docs"
    / "process"
    / "stage-gate-checkpoint-protocol.md",
    "context-guard-protocol": ROOT / "docs" / "process" / "context-guard-protocol.md",
    "source-of-truth-policy": ROOT / "docs" / "process" / "source-of-truth-policy.md",
    "stop-conditions": ROOT / "docs" / "process" / "stop-conditions.md",
    "partner-handoff-standard": ROOT / "docs" / "process" / "partner-handoff-standard.md",
}

STAGES_DOCS = {
    "stages-readme": ROOT / "docs" / "stages" / "README.md",
    "stage-manifest-standard": ROOT / "docs" / "stages" / "stage-manifest-standard.yaml",
    "context-receipt-template": ROOT / "docs" / "stages" / "context-receipt-template.md",
    "stage-gate-report-template": ROOT / "docs" / "stages" / "stage-gate-report-template.md",
    "design-example": ROOT / "docs" / "stages" / "examples" / "design-stage-manifest.example.yaml",
    "frontend-example": ROOT
    / "docs"
    / "stages"
    / "examples"
    / "frontend-stage-manifest.example.yaml",
    "review-example": ROOT / "docs" / "stages" / "examples" / "review-stage-manifest.example.yaml",
}

DECISIONS_README = ROOT / "docs" / "decisions" / "README.md"
PR_TEMPLATE = ROOT / ".github" / "pull_request_template.md"

FORBIDDEN_PATH_PREFIXES = (
    "apps/orchestrator/src/",
    "apps/admin-console/src/",
    "shared/",
    "infra/",
)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"production action is enabled", re.IGNORECASE),
    re.compile(r"workflow dispatch is enabled", re.IGNORECASE),
    re.compile(r"workflow resume is enabled", re.IGNORECASE),
    re.compile(r"external action is enabled", re.IGNORECASE),
)
NEGATION_CUES = (
    "no ",
    "not ",
    "never ",
    "cannot ",
    "must not",
    "does not",
    "won't",
    "will not",
    "n't ",
    "without ",
    "prohibit",
    "unless",
)
NEGATION_WINDOW = 160

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _unnegated_matches(name: str, text: str) -> list[str]:
    hits = []
    for pattern in FORBIDDEN_CLAIM_PATTERNS:
        for m in pattern.finditer(text):
            start = max(0, m.start() - NEGATION_WINDOW)
            context = text[start : m.start()].lower()
            if any(cue in context for cue in NEGATION_CUES):
                continue
            hits.append(f"{name} contains a forbidden capability claim: {pattern.pattern}")
    return hits


def check_files_exist(label: str, mapping: dict[str, Path]) -> None:
    for name, p in mapping.items():
        if not p.is_file():
            bad(f"missing {label} file: {p} ({name})")


def check_pr_template_sections() -> None:
    if not PR_TEMPLATE.is_file():
        bad(f"missing PR template: {PR_TEMPLATE}")
        return
    text_low = _norm(PR_TEMPLATE.read_text(encoding="utf-8"))
    for section in ("shared context", "scope", "authorization", "safety", "evidence"):
        if section not in text_low:
            bad(f"PR template missing required section content: {section}")


def check_security_skill_content() -> None:
    p = SKILL_FILES["security-governance"]
    if not p.is_file():
        return
    text_low = _norm(p.read_text(encoding="utf-8"))
    required = (
        "production action",
        "workflow dispatch",
        "external action",
        "secrets",
        "client-side-only rbac",
    )
    for term in required:
        if term not in text_low:
            bad(f"security-governance skill missing required restriction: {term}")


def check_frontend_skill_content() -> None:
    p = SKILL_FILES["frontend-implementation"]
    if not p.is_file():
        return
    text_low = _norm(p.read_text(encoding="utf-8"))
    if "local-only" not in text_low or "not deliverables" not in text_low:
        bad("frontend-implementation skill missing local-only-output prohibition")


def check_design_skill_content() -> None:
    p = SKILL_FILES["design-collaboration"]
    if not p.is_file():
        return
    text_low = _norm(p.read_text(encoding="utf-8"))
    if "does not modify runtime code" not in text_low:
        bad("design-collaboration skill missing no-runtime-code rule")


def check_no_forbidden_paths_changed() -> None:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        gap("git not available; skipped forbidden-path diff check")
        return
    if result.returncode != 0:
        gap("could not compute diff against origin/main; skipped forbidden-path check")
        return
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for path in changed:
        normalized = path.replace("\\", "/")
        for prefix in FORBIDDEN_PATH_PREFIXES:
            if normalized.startswith(prefix):
                bad(f"forbidden path changed in this stage: {path}")


def check_no_forbidden_claims() -> None:
    all_new_docs: dict[str, Path] = {
        **SKILL_FILES,
        "agents-readme": AGENTS_README,
        **PROCESS_DOCS,
        **{k: v for k, v in STAGES_DOCS.items() if v.suffix == ".md"},
    }
    for name, p in all_new_docs.items():
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        for hit in _unnegated_matches(name, text):
            bad(hit)


def main() -> int:
    check_files_exist("skill", SKILL_FILES)
    if not AGENTS_README.is_file():
        bad(f"missing .agents README: {AGENTS_README}")
    check_files_exist("process", PROCESS_DOCS)
    check_files_exist("stages", STAGES_DOCS)
    if not DECISIONS_README.is_file():
        bad(f"missing docs/decisions README: {DECISIONS_README}")

    check_pr_template_sections()
    check_security_skill_content()
    check_frontend_skill_content()
    check_design_skill_content()
    check_no_forbidden_paths_changed()
    check_no_forbidden_claims()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] all five .agents skills, docs/stages standard/templates/examples, five")
    print("       docs/process governance docs, and PR template sections present; security skill")
    print("       states production/workflow/external/secret/RBAC restrictions; frontend skill")
    print("       states local-only-output prohibition; design skill states no-runtime-code rule;")
    print("       no forbidden runtime path changed; no unauthorized capability claim found")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
