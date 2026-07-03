#!/usr/bin/env python3
"""Step 65A -- Staging functional coverage & integration readiness assessment verifier.

Confirms the assessment docs exist and cover every functional domain with classification statuses,
register the gaps + integration readiness (disabled/mocked), define the 65B-65I roadmap with user
authorization gates, record the 64F.4 pause + 64->65 transition, and assert this is assessment-only
(no runtime change, no integration enablement, no production action; production_executed stays 0).

Marker: STAGING_FUNCTIONAL_COVERAGE_ASSESSMENT_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
MATRIX = STAGING / "staging-functional-coverage-matrix.md"
GAPS = STAGING / "staging-functional-gap-register.md"
INTEG = STAGING / "staging-integration-readiness-assessment.md"
ROADMAP = STAGING / "staging-functional-validation-roadmap.md"
CRITERIA = STAGING / "staging-functional-acceptance-criteria.md"
UVP = STAGING / "staging-user-validation-points.md"
RISKS = STAGING / "staging-functional-validation-risk-register.md"
TRANSITION = STAGING / "step64-to-step65-transition-note.md"

MARKER = "STAGING_FUNCTIONAL_COVERAGE_ASSESSMENT_VERIFY"

DOCS = {
    "coverage-matrix": MATRIX,
    "gap-register": GAPS,
    "integration-readiness": INTEG,
    "validation-roadmap": ROADMAP,
    "acceptance-criteria": CRITERIA,
    "user-validation-points": UVP,
    "risk-register": RISKS,
    "transition-note": TRANSITION,
}
# Functional domains (section 6) that must appear in the coverage matrix.
DOMAINS = (
    "intake",
    "agent pipeline",
    "workflow orchestration",
    "qa / code",
    "audit",
    "governance",
    "retry",
    "external integrations",
    "admin console",
    "deployment",
)
# Classification status values that must be documented.
STATUSES = (
    "staging_validated",
    "test_validated_only",
    "seeded_evidence_only",
    "mocked",
    "disabled",
    "blocked_by_credential",
    "blocked_by_authorization",
)
# Step 65 roadmap items.
ROADMAP_STEPS = ("65b", "65c", "65d", "65e", "65f", "65g", "65h", "65i")

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()
    matrix_low = texts["coverage-matrix"].lower()

    # All domains + classification statuses present in the matrix.
    for dom in DOMAINS:
        if dom not in matrix_low:
            bad(f"coverage matrix does not cover domain: {dom}")
    for st in STATUSES:
        if st not in matrix_low:
            bad(f"coverage matrix does not use status value: {st}")
    for field in ("acceptance criteria", "blocking gap", "priority"):
        if field not in matrix_low:
            bad(f"coverage matrix missing classification field: {field}")

    # Roadmap defines 65B-65I.
    roadmap_low = texts["validation-roadmap"].lower()
    for step in ROADMAP_STEPS:
        if step not in roadmap_low:
            bad(f"validation roadmap missing {step.upper()}")

    # 64F.4 paused + transition documented.
    if "64f.4" not in low or "paused" not in low:
        bad("docs do not document that Step 64F.4 is paused")
    if "step 65" not in low:
        bad("docs do not document the Step 65 functional-validation track")

    # External integrations disabled/mocked documented.
    if "disabled" not in texts["integration-readiness"].lower() or (
        "mock" not in texts["integration-readiness"].lower()
    ):
        bad("integration readiness does not document disabled/mocked integrations")

    # User authorization gates documented.
    uvp_low = texts["user-validation-points"].lower()
    if "authoriz" not in uvp_low or "verdict" not in uvp_low:
        bad("user validation points do not document authorization gates / acceptance verdict")
    if "step 64e" not in low or "pass" not in low:
        bad("docs do not record Step 64E: PASS")

    # Assessment-only: no runtime change / no production action; prod_exec 0; flags; no secrets.
    if "no runtime change" not in low:
        bad("docs do not state no runtime change occurred")
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")
        for flag in ("production-action=false", "image-push=false", "live-integrations=disabled"):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "image-push=true", "production-ready=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    # Tracked UNKNOWN items -> PASS_WITH_GAPS (explicitly allowed by the spec).
    result = "PASS_WITH_GAPS" if "unknown" in matrix_low else "PASS"
    print(
        "  [OK] coverage matrix (domains A-J + statuses) + gap register + integration readiness +"
    )
    print("       65B-65I roadmap + acceptance criteria + user validation points + risk register +")
    print("       transition note; 64F.4 paused; integrations disabled/mocked; no runtime change;")
    print("       no production action; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
