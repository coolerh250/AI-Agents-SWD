"""Stage 49 -- build the human-readable delivery package sections.

Produces the 14 required sections from already-persisted mini delivery pilot
evidence. Never re-runs code generation or tests. Section content carries
summaries / counts / refs only -- never raw code bodies, secrets, or
chain-of-thought. A section whose evidence is genuinely missing is marked
``missing`` (not ``ready``).
"""

from __future__ import annotations

from shared.sdk.delivery_package.models import REQUIRED_SECTION_KEYS, DeliveryPackageSection

KNOWN_LIMITATIONS = [
    "No authentication / authorization (out of scope).",
    "Local SQLite only; not multi-user / not horizontally scalable.",
    "No production deployment configuration in this stage.",
    "No real GitHub PR in this stage (controlled-only).",
    "No external delivery / notification in this stage.",
    "Controlled-only workspace; generated files are not committed to the main repo.",
]

NEXT_STEPS = [
    "Operator reviews the acceptance checklist and accepts / requests changes.",
    "Step 48 Admin Console v0 (read-only delivery visibility).",
    "Step 49 Backup / DR gap closure before any production delivery.",
]

RUN_INSTRUCTIONS = [
    "python -m venv .venv && source .venv/bin/activate",
    "pip install -r requirements.txt",
    "uvicorn app.main:app --reload",
    "pytest -q",
]

_TITLES = {
    "executive_summary": "Executive summary",
    "scope_and_non_scope": "Scope and non-scope",
    "project_plan": "Project plan",
    "design_review_summary": "Design review summary",
    "implementation_summary": "Implementation summary",
    "generated_files_manifest": "Generated files manifest",
    "test_results": "Test results",
    "qa_summary": "QA summary",
    "safety_summary": "Safety summary",
    "acceptance_checklist": "Acceptance checklist",
    "known_limitations": "Known limitations",
    "run_instructions": "Run instructions",
    "handoff_notes": "Handoff notes",
    "next_steps": "Next steps",
}


def build_sections(evidence: dict, checklist: dict) -> list[DeliveryPackageSection]:
    """Build the 14 required sections (order preserved via order_index)."""
    pilot = evidence.get("pilot") or {}
    project = evidence.get("project") or {}
    review = evidence.get("review") or {}
    workspace_report = evidence.get("workspace_report") or {}
    files = workspace_report.get("files") or []
    test_runs = workspace_report.get("test_runs") or []
    qa = evidence.get("qa") or {}
    safety = evidence.get("safety") or {}
    acc = evidence.get("acceptance_summary") or {}
    pilot_type = pilot.get("pilot_type") or "fastapi_todo_service"

    pytest_run: dict = next((t for t in test_runs if t.get("test_type") == "pytest"), {})

    contents: dict[str, dict] = {
        "executive_summary": {
            "summary": (
                f"Controlled delivery package for {pilot_type}: project planned, design "
                f"reviewed, controlled workspace generated + tested. QA={qa.get('status')}, "
                f"safety={safety.get('status')}, acceptance "
                f"{acc.get('satisfied', 0)}/{acc.get('total', 0)} satisfied. Ready for "
                f"operator review. No PR, no deploy, no real LLM; production_executed=false."
            ),
            "human_acceptance_required": True,
        },
        "scope_and_non_scope": {
            "in_scope": [
                "Controlled FastAPI Todo workspace generation",
                "Automated tests + static checks",
                "Acceptance / QA / safety evidence",
            ],
            "out_of_scope": [
                "Real GitHub PR / merge",
                "Production deployment",
                "External delivery / notification",
                "Authentication / authorization",
            ],
        },
        "project_plan": {
            "project_id": evidence.get("project_id"),
            "title": project.get("title"),
            "project_type": project.get("project_type"),
            "work_items_count": len(evidence.get("work_items") or []),
        },
        "design_review_summary": {
            "design_review_session_id": evidence.get("design_review_session_id"),
            "decision": review.get("decision"),
            "blocking_findings_count": evidence.get("blocking_findings_count", 0),
        },
        "implementation_summary": {
            "workspace_id": evidence.get("workspace_id"),
            "generated_files_count": len(files),
            "tests_status": pytest_run.get("status"),
        },
        "generated_files_manifest": {
            "files": [
                {
                    "relative_path": f.get("relative_path"),
                    "content_hash": f.get("content_hash"),
                    "size_bytes": f.get("size_bytes"),
                }
                for f in files
            ],
            "files_count": len(files),
        },
        "test_results": {
            "test_runs": [
                {
                    "test_type": t.get("test_type"),
                    "status": t.get("status"),
                    "tests_total": t.get("tests_total"),
                    "tests_passed": t.get("tests_passed"),
                    "tests_failed": t.get("tests_failed"),
                }
                for t in test_runs
            ],
        },
        "qa_summary": {
            "status": qa.get("status"),
            "tests_total": qa.get("tests_total"),
            "tests_passed": qa.get("tests_passed"),
            "tests_failed": qa.get("tests_failed"),
            "static_checks_status": qa.get("static_checks_status"),
            "findings": qa.get("findings") or [],
        },
        "safety_summary": {
            "status": safety.get("status"),
            "production_executed_count": safety.get("production_executed_count", 0),
            "github_write_performed": safety.get("github_write_performed", False),
            "pr_created": safety.get("pr_created", False),
            "deployment_performed": safety.get("deployment_performed", False),
            "real_llm_used": safety.get("real_llm_used", False),
            "repo_root_modified": safety.get("repo_root_modified", False),
            "secret_leak_detected": safety.get("secret_leak_detected", False),
            "chain_of_thought_persisted": safety.get("chain_of_thought_persisted", False),
        },
        "acceptance_checklist": checklist,
        "known_limitations": {"limitations": list(KNOWN_LIMITATIONS)},
        "run_instructions": {"steps": list(RUN_INSTRUCTIONS)},
        "handoff_notes": {
            "notes": (
                "This is a controlled-only delivery package awaiting human operator "
                "acceptance. It does not represent a production-ready or externally "
                "delivered system."
            ),
        },
        "next_steps": {"next_steps": list(NEXT_STEPS)},
    }

    # A section is ``ready`` when its evidence is present; ``missing`` otherwise.
    def _ready(key: str) -> bool:
        if key == "generated_files_manifest":
            return len(files) > 0
        if key == "test_results":
            return len(test_runs) > 0
        if key == "qa_summary":
            return bool(qa.get("status"))
        if key == "safety_summary":
            return bool(safety.get("status"))
        if key == "design_review_summary":
            return bool(evidence.get("design_review_session_id"))
        if key == "project_plan":
            return bool(evidence.get("project_id"))
        if key == "implementation_summary":
            return bool(evidence.get("workspace_id"))
        if key == "acceptance_checklist":
            return bool(checklist.get("items"))
        return True

    sections: list[DeliveryPackageSection] = []
    for idx, key in enumerate(REQUIRED_SECTION_KEYS):
        ready = _ready(key)
        sections.append(
            DeliveryPackageSection(
                section_key=key,
                title=_TITLES[key],
                content=contents[key],
                content_summary=_summarize(key, contents[key]),
                order_index=idx,
                status="ready" if ready else "missing",
            )
        )
    return sections


def _summarize(key: str, content: dict) -> str:
    if key == "executive_summary":
        return str(content.get("summary", ""))[:500]
    if key == "known_limitations":
        return f"{len(content.get('limitations', []))} documented limitations"
    if key == "run_instructions":
        return f"{len(content.get('steps', []))} run steps"
    if key == "next_steps":
        return f"{len(content.get('next_steps', []))} next steps"
    if key == "acceptance_checklist":
        return f"{len(content.get('items', []))} checklist items"
    return _TITLES.get(key, key)


__all__ = ["build_sections", "KNOWN_LIMITATIONS", "NEXT_STEPS", "RUN_INSTRUCTIONS"]
