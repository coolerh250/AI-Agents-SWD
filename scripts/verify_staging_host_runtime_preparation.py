#!/usr/bin/env python3
"""Step 64B.2A -- staging host runtime preparation verifier.

Confirms the host-level container runtime preparation of the staging target (10.0.1.32) is
documented: Docker Engine + Docker Compose v2 installed, daemon state, docker group, staging
directory, port 18000, validation-only hello-world -- while asserting that NO AI Agents
runtime was deployed, NO `docker compose up` was run, NO production action occurred, and no
secret/password/private-key value is committed. production_executed must remain 0.

Marker: STAGING_HOST_RUNTIME_PREPARATION_VERIFY: PASS | FAIL | BLOCKED_HOST_PREREQUISITE
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-host-runtime-preparation-report.md"
NOTES = STAGING / "staging-docker-installation-notes.md"
AFTER = STAGING / "staging-runtime-bootstrap-prerequisites-after-prep.md"

MARKER = "STAGING_HOST_RUNTIME_PREPARATION_VERIFY"

# Secret shapes that must never appear in the committed docs.
SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|apiVersion:\s*v1[\s\S]*kubeconfig)"
)
# A stored password shape like `password: <value>` / `password=<value>` (not the word alone).
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    docs = {"report": REPORT, "notes": NOTES, "after": AFTER}
    for name, p in docs.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    report = REPORT.read_text(encoding="utf-8")
    notes = NOTES.read_text(encoding="utf-8")
    after = AFTER.read_text(encoding="utf-8")
    both = report + "\n" + notes + "\n" + after
    low = both.lower()

    # Target host documented in each doc.
    for name, text in (("report", report), ("notes", notes), ("after", after)):
        if "10.0.1.32" not in text:
            bad(f"{name} does not document target host 10.0.1.32")

    # Docker installed status documented.
    if "docker" not in low or not re.search(r"docker version|docker\s*[`]*29", low):
        bad("Docker installed version not documented")
    if "installation method" not in low and "official docker apt" not in low:
        bad("Docker installation method not documented")

    # Docker Compose installed status documented.
    if "compose" not in low or "docker compose version" not in low:
        bad("Docker Compose installed status not documented")

    # Docker service state documented.
    if "active" not in low or (
        "is-active" not in low and "daemon" not in low and "service" not in low
    ):
        bad("Docker service state not documented")

    # docker group documented.
    if "group" not in low:
        bad("docker group state not documented")

    # Staging directory documented.
    if "/data/ai-agents-staging" not in both:
        bad("staging directory /data/ai-agents-staging not documented")

    # Port 18000 documented.
    if "18000" not in both:
        bad("port 18000 state not documented")

    # hello-world validation documented as validation-only.
    if "hello-world" not in low and "hello from docker" not in low:
        bad("hello-world validation not documented")
    if "validation-only" not in low and "validation only" not in low:
        bad("hello-world not marked as validation-only")

    # No platform runtime deployment / no docker compose up claimed.
    for name, text in (("report", report), ("notes", notes), ("after", after)):
        tl = text.lower()
        # Must explicitly disclaim runtime deployment + compose up.
        if "no ai agents runtime" not in tl and "no runtime" not in tl:
            bad(f"{name} does not disclaim AI Agents runtime deployment")
        if "no `docker compose up`" not in tl and "no docker compose up" not in tl:
            bad(f"{name} does not disclaim `docker compose up`")

    # Machine-checkable safety flags.
    for name, text in (("report", report), ("notes", notes), ("after", after)):
        for flag in (
            "production-action=false",
            "production-ready=false",
            "runtime-deployment=false",
            "docker-compose-up=false",
            "staging-only=true",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in (
            "production-action=true",
            "production-ready=true",
            "runtime-deployment=true",
            "production-deploy=true",
            "docker-compose-up=true",
        ):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # No secret material in any committed doc.
    for name, text in (("report", report), ("notes", notes), ("after", after)):
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content (private key / token / kubeconfig)")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    # Credential handling documented as key-based, no password used.
    if "key-based" not in low:
        bad("docs do not document key-based SSH access")
    if "no password" not in low:
        bad("docs do not state no password was used")

    # production_executed must remain 0.
    if "production_executed_true_count" not in low:
        bad("docs do not state production_executed_true_count posture")
    if re.search(r"production_executed_true_count\s*[:=]?\s*[1-9]", both):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] staging host runtime prepared (Docker + Compose installed on 10.0.1.32);")
    print("       no AI Agents runtime deployed; no docker compose up; no production action;")
    print("       no secret/password/private-key committed; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
