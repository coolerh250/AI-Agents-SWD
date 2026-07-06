#!/usr/bin/env python3
"""Step 65D -- Controlled GitHub sandbox validation verifier.

Confirms the 65D docs record a real, controlled sandbox draft-PR validation: a draft PR created in
the non-production sandbox repo, the control path + flow fix documented, staging reset to safe, and
strict no-secret-values / no-merge / no-production-action guarantees (production_executed stays 0).

Marker: CONTROLLED_GITHUB_SANDBOX_VALIDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-github-sandbox-validation-report.md"
EVIDENCE = STAGING / "controlled-github-sandbox-validation-evidence.md"
SAFETY = STAGING / "controlled-github-sandbox-safety-record.md"
GAPS = STAGING / "controlled-github-sandbox-known-gaps.md"

MARKER = "CONTROLLED_GITHUB_SANDBOX_VALIDATION_VERIFY"

DOCS = {"report": REPORT, "evidence": EVIDENCE, "safety-record": SAFETY, "known-gaps": GAPS}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

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
    report_low = texts["report"].lower()

    # A real draft PR was created in the sandbox repo.
    if "pr #15" not in report_low and "pull/15" not in report_low:
        bad("report does not record the created draft PR (#15)")
    if "ai-agents-swd-sandbox" not in low:
        bad("docs do not name the sandbox repo AI-Agents-SWD-sandbox")
    if "draft" not in report_low or "created" not in report_low:
        bad("report does not record a created draft PR")

    # Control path + flow fix documented.
    if "allowlist" not in low or "csrf" not in low:
        bad("docs do not record the controlled path (allowlist + auth/CSRF)")
    if "no commits" not in low or "evidence" not in low:
        bad("docs do not document the no-commit flow fix (evidence commit)")

    # Reset to safe documented.
    if "reset" not in low or "sandbox_github_live=false" not in low:
        bad("docs do not document reset to safe (SANDBOX_GITHUB_LIVE=false)")

    # No merge / no production action; prod_exec 0; flags; no secret values.
    if "no merge" not in low:
        bad("docs do not state no merge")
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")
        for flag in ("production-action=false", "github-merge=false", "image-push=false"):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "github-merge=true", "image-push=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] real controlled sandbox draft PR #15 created in AI-Agents-SWD-sandbox; path +")
    print("       flow fix documented; reset to safe; no merge, no production action, no secret")
    print("       values; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
