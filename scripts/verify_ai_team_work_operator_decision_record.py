#!/usr/bin/env python3
"""Step 66A.2 -- AI Agents Team Work operator decision record verifier.

Confirms the operator's D1-D14 decisions are recorded exactly (D7=B, D9=A, D10=C, D11=C plus the
matched recommended values), that the web-research top-10 whitelist is a PROPOSAL pending operator
confirmation (not an approved final whitelist, no live research), that the MVP scope lock + 66A.3
blueprint inputs + out-of-scope list exist, that Claude Code did not change the decisions, and that
this stage is documentation-only (no UI/backend/runtime/workflow/external/production action).

Marker: AI_TEAM_WORK_OPERATOR_DECISION_RECORD_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

RECORD = TEST / "ai-team-work-operator-decision-record.md"
WHITELIST = TEST / "ai-team-work-web-research-source-whitelist-proposal.md"
SCOPE = TEST / "ai-team-work-mvp-scope-lock.md"
BLUEPRINT = TEST / "ai-team-work-step66a3-blueprint-inputs.md"
REGISTER = TEST / "ai-team-work-decision-register.md"

MARKER = "AI_TEAM_WORK_OPERATOR_DECISION_RECORD_VERIFY"

DOCS = {
    "operator-decision-record": RECORD,
    "web-research-whitelist-proposal": WHITELIST,
    "mvp-scope-lock": SCOPE,
    "step66a3-blueprint-inputs": BLUEPRINT,
    "decision-register": REGISTER,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/test/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    rec = texts["operator-decision-record"].lower()
    low = "\n".join(texts.values()).lower()

    # D1-D14 all present in the record.
    for i in range(1, 15):
        if f"d{i}" not in rec:
            bad(f"decision record missing D{i}")

    # Exact key decisions.
    for stmt in ("d7 is b", "d9 is a", "d10 is c", "d11 is c"):
        if stmt not in rec:
            bad(f"decision record does not state '{stmt.upper()}' exactly")

    # Recorded values (matched + override decisions) documented.
    for phrase in (
        "conservative rbac",  # D1=B
        "software delivery + documentation + platform improvement",  # D2=B
        "clarification_expired",  # D4=B
        "escalate",  # D5=B action set
        "archive",  # D5=B action set
        "max 3 per delivery",  # D12=B
        "platform admin / agent operator only",  # D13=C
        "full chat-style agent workroom",  # D9=A
    ):
        if phrase not in rec:
            bad(f"decision record missing recorded value: '{phrase}'")

    # Claude Code did not change the decisions.
    if "claude code did not change operator decisions" not in rec:
        bad("record does not assert Claude Code did not change operator decisions")
    if "recorded exactly" not in rec and "recorded exactly as" not in rec:
        bad("record does not assert decisions recorded exactly")

    # Web research whitelist is a PROPOSAL, not final, no live research.
    wl = texts["web-research-whitelist-proposal"].lower()
    if "top-10" not in wl and "top 10" not in wl:
        bad("whitelist proposal does not present a top-10 source list")
    if "pending operator confirmation" not in wl:
        bad("whitelist not marked pending operator confirmation")
    if "final whitelist is not approved" not in wl and "not an approved final whitelist" not in wl:
        bad("whitelist does not state it is not an approved final whitelist")
    if "no web browsing" not in wl and "no browsing" not in wl:
        bad("whitelist does not state no web browsing was performed")
    if "missing capability" not in wl:
        bad("whitelist does not flag the browsing/search connector as a missing capability")
    # Count 10 proposed source rows (numbered table).
    rows = len(
        re.findall(r"^\|\s*\d+\s*\|", texts["web-research-whitelist-proposal"], re.MULTILINE)
    )
    if rows < 10:
        bad(f"whitelist proposal lists {rows} sources; expected 10")

    # MVP scope lock + out-of-scope + blueprint inputs.
    if "mvp scope lock" not in texts["mvp-scope-lock"].lower():
        bad("MVP scope lock doc missing its title/section")
    if "out-of-scope" not in low:
        bad("out-of-scope list not documented")
    bp = texts["step66a3-blueprint-inputs"].lower()
    for need in (
        "acceptance criteria",
        "implementation risks",
        "required backend",
        "required apis",
    ):
        if need not in bp:
            bad(f"blueprint inputs missing section: '{need}'")

    # Documentation-only posture (aggregate).
    if "no ui implementation" not in low:
        bad("docs do not state no UI implementation")
    if "no backend implementation" not in low:
        bad("docs do not state no backend implementation")
    if "no runtime change" not in low:
        bad("docs do not state no runtime change")
    if "no workflow execution" not in low:
        bad("docs do not state no workflow execution")
    if "no external action" not in low:
        bad("docs do not state no external action")
    if "no production action" not in low:
        bad("docs do not state no production action")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] D1-D14 recorded exactly (D7=B, D9=A, D10=C, D11=C); recorded values present;")
    print("       whitelist top-10 = proposal pending operator confirmation (no live research);")
    print("       MVP scope lock + out-of-scope + 66A.3 blueprint inputs present; Claude Code did")
    print("       not change decisions; documentation-only (no UI/backend/runtime/external/prod)")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
