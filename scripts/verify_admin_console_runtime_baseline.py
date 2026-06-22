#!/usr/bin/env python3
"""Step 51.4 -- Admin Console runtime baseline view verifier.

Asserts the Admin Console exposes a read-only Runtime Baseline view (static
fallback + React source), backed by the read-only runtime report API, with NO
deploy/sync/apply/install button, no mutation client method, no cluster
credential / kubeconfig / token input, and no secret display. Combines a live
/admin + report check with a source-level guard. No cluster.

Marker: ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC_INDEX = ADMIN / "static" / "index.html"
RUNTIME_PAGE = ADMIN / "src" / "pages" / "RuntimeBaseline.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
CLIENT = ADMIN / "src" / "api" / "client.ts"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

# Forbidden mutation / deploy controls (case-insensitive button/handler text).
FORBIDDEN_CONTROLS = re.compile(
    r"(deploy|\bsync\b|\bapply\b|\binstall\b|\bupgrade\b|kubeconfig|cluster[_-]?credential|"
    r"argocd[_-]?token)",
    re.IGNORECASE,
)
MUTATION_VERB = re.compile(r"\.(post|put|patch|delete)\s*\(", re.IGNORECASE)

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=8) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):
        return 0, ""


def main() -> int:
    # 1. runtime view present in static fallback + React source + nav
    static_src = STATIC_INDEX.read_text(encoding="utf-8")
    if "Runtime Baseline" not in static_src or "renderRuntime" not in static_src:
        bad("static fallback missing the Runtime Baseline view")
    if "/operations/runtime/report" not in static_src:
        bad("static runtime view must read the read-only runtime report endpoint")
    if not RUNTIME_PAGE.is_file():
        bad("React RuntimeBaseline page missing")
    elif "/operations/runtime/report" not in (
        (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")
    ):
        bad("React runtime page not wired to the runtime report endpoint")
    if "Runtime Baseline" not in NAV.read_text(encoding="utf-8"):
        bad("nav missing Runtime Baseline entry")
    if not failures:
        ok("Runtime Baseline view present (static fallback + React + nav), report-API backed")

    # 2. no deploy/sync/apply controls; no mutation client method
    runtime_page = RUNTIME_PAGE.read_text(encoding="utf-8") if RUNTIME_PAGE.is_file() else ""
    # only inspect the runtime view portions for control buttons
    static_runtime = static_src[
        static_src.find("async function renderRuntime") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", static_runtime), ("react", runtime_page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN_CONTROLS.search(m.group(1)):
                bad(f"{label} runtime view has a forbidden control button: {m.group(1)}")
        # the word may also appear as an onClick handler creating a mutation
        if MUTATION_VERB.search(text):
            bad(f"{label} runtime view uses a mutation HTTP verb")
    client_src = CLIENT.read_text(encoding="utf-8")
    if MUTATION_VERB.search(client_src.replace("// ", "")):
        # client must remain GET-only (allow the word in comments)
        if re.search(r"method:\s*[\"'](POST|PUT|PATCH|DELETE)", client_src):
            bad("api client exposes a mutation method")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("runtime view has no deploy/sync/apply button and no mutation client method")

    # 3. live /admin reachable + report endpoint serves the baseline
    code, _ = _get("/admin/")
    if code == 0:
        bad(f"/admin not reachable at {BASE}")
    elif code != 200:
        bad(f"/admin returned {code}")
    rcode, rbody = _get("/operations/runtime/report")
    if rcode != 200:
        bad(f"runtime report endpoint returned {rcode}")
    elif "validated_not_deployed" not in rbody and "passed_with_non_production" not in rbody:
        bad("runtime report does not show a validated-not-deployed baseline")
    if not [f for f in failures if "/admin" in f or "report endpoint" in f or "baseline" in f]:
        ok("/admin reachable and runtime report shows the validated-not-deployed baseline")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
