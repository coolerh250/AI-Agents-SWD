#!/usr/bin/env python3
"""Step 65B -- Controlled staging external integration plan verifier.

Confirms the integration-plan package exists and documents: the in-scope integrations (GitHub
sandbox / notification / LLM / staging secret backend), the deferred integrations (registry / cloud
storage), 65C-65I authorization gates, a user-input checklist, and a risk register -- with strict
no-secret-values / no-enablement / no-external-write / no-production-action guarantees
(production_executed stays 0). Planning only.

Marker: CONTROLLED_EXTERNAL_INTEGRATION_PLAN_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
PLAN = STAGING / "controlled-external-integration-plan.md"
SECRET = STAGING / "staging-secret-backend-plan.md"
GITHUB = STAGING / "github-sandbox-integration-plan.md"
NOTIF = STAGING / "notification-staging-channel-plan.md"
LLM = STAGING / "llm-staging-integration-plan.md"
DEFERRED = STAGING / "deferred-integration-register.md"
GATES = STAGING / "external-integration-authorization-gates.md"
CHECKLIST = STAGING / "external-integration-user-input-checklist.md"
RISKS = STAGING / "external-integration-risk-register.md"

MARKER = "CONTROLLED_EXTERNAL_INTEGRATION_PLAN_VERIFY"

DOCS = {
    "integration-plan": PLAN,
    "secret-backend-plan": SECRET,
    "github-sandbox-plan": GITHUB,
    "notification-plan": NOTIF,
    "llm-plan": LLM,
    "deferred-register": DEFERRED,
    "authorization-gates": GATES,
    "user-input-checklist": CHECKLIST,
    "risk-register": RISKS,
}
IN_SCOPE = (
    "github sandbox",
    "notification staging channel",
    "llm staging key",
    "staging secret backend",
)
GATE_STEPS = ("65c", "65d", "65e", "65f", "65g", "65h", "65i")

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,})"
)
# A stored secret value assignment (name = value). Reference names alone are fine.
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/_\-]{12,}", re.I
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
    plan_low = texts["integration-plan"].lower()

    # In-scope integrations documented in the master plan.
    for item in IN_SCOPE:
        if item not in plan_low:
            bad(f"master plan does not document in-scope integration: {item}")

    # Deferred integrations documented.
    def_low = texts["deferred-register"].lower()
    if "container registry" not in def_low or "defer" not in def_low:
        bad("deferred register does not document container registry sandbox as deferred")
    if "cloud storage" not in def_low and "google drive" not in def_low:
        bad("deferred register does not document cloud storage / Google Drive as deferred")

    # Authorization gates for 65C-65I + secret handling rules.
    gates_low = texts["authorization-gates"].lower()
    for step in GATE_STEPS:
        if step not in gates_low:
            bad(f"authorization gates missing {step.upper()}")
    sec_low = texts["secret-backend-plan"].lower()
    if "no secret values may be committed" not in sec_low or "non-production" not in sec_low:
        bad("secret backend plan is missing the no-secret-in-repo / non-production rules")

    # User-input checklist separates needed-later from do-not-provide-now.
    chk_low = texts["user-input-checklist"].lower()
    if "needed later" not in chk_low or "not to be provided" not in chk_low:
        bad("user-input checklist does not separate needed-later from do-not-provide-now")

    # Status posture.
    if "no integration enabled" not in low:
        bad("docs do not state no integration enabled")
    if "no runtime change" not in low:
        bad("docs do not state no runtime change")

    # Per-doc: no production action / no external write / prod_exec 0 / flags / no secret values.
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
        if "no external write" not in tl:
            bad(f"{name} does not state no external write")
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
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    # Tracked placeholders -> PASS_WITH_GAPS (explicitly allowed by the spec).
    result = "PASS_WITH_GAPS" if "placeholder" in low else "PASS"
    print(
        "  [OK] master plan + secret backend + GitHub/notification/LLM plans + deferred register +"
    )
    print("       65C-65I gates + user-input checklist + risk register; no secret values; no")
    print("       integration enabled; no external write; no runtime change; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
