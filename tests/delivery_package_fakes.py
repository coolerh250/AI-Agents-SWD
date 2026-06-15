"""Stage 49 -- in-memory fakes + helpers for delivery package tests."""

from __future__ import annotations

import uuid


def _id() -> str:
    return str(uuid.uuid4())


async def build_fake_package(tmp_path, monkeypatch, *, package_store=None):
    """Run a fake mini pilot, then build a delivery package against fakes.

    Returns (result, stores) where stores is a dict of the fake stores used,
    including the ``package`` store and the completed ``pilot`` id.
    """
    from mini_delivery_fakes import run_fake_pilot

    from shared.sdk.delivery_package import DeliveryPackageRequest, run_delivery_package_build

    pilot_result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    stores["package"] = package_store or FakeDeliveryPackageStore()

    result = await run_delivery_package_build(
        request=DeliveryPackageRequest(pilot_id=pilot_result.pilot_id),
        pilot_store=stores["pilot"],
        project_store=stores["project"],
        review_store=stores["review"],
        workspace_store=stores["workspace"],
        package_store=stores["package"],
        emit_events=False,
    )
    stores["pilot_result"] = pilot_result
    return result, stores


class FakeDeliveryPackageStore:
    def __init__(self) -> None:
        self.packages: dict[str, dict] = {}
        self.sections: dict[str, list] = {}
        self.artifacts: dict[str, list] = {}
        self.gate_runs: dict[str, dict] = {}
        self.gate_checks: dict[str, list] = {}
        self.operator_reviews: dict[str, dict] = {}
        self.handoffs: dict[str, list] = {}
        self.readiness: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}
        self.export_metadata: dict[str, dict] = {}
        self._order: list[str] = []

    # ---- create ----
    async def create_delivery_package(self, package) -> str:
        pid = _id()
        self.packages[pid] = {
            "id": pid,
            "package_key": package.package_key,
            "package_type": package.package_type,
            "status": package.status,
            "project_id": package.project_id,
            "pilot_id": package.pilot_id,
            "workspace_id": package.workspace_id,
            "design_review_session_id": package.design_review_session_id,
            "controlled_only": package.controlled_only,
            "human_acceptance_required": package.human_acceptance_required,
            "human_acceptance_status": package.human_acceptance_status,
            "real_llm_enabled": package.real_llm_enabled,
            "github_write_enabled": package.github_write_enabled,
            "pr_creation_enabled": package.pr_creation_enabled,
            "deployment_enabled": package.deployment_enabled,
            "external_delivery_enabled": package.external_delivery_enabled,
            "production_executed": package.production_executed,
            "created_by_agent": package.created_by_agent,
            "created_at": "2026-06-15T00:00:00+00:00",
            "completed_at": None,
            "metadata": dict(package.metadata or {}),
        }
        self._order.insert(0, pid)
        return pid

    async def update_package_status(self, package_id, status, *, completed=False) -> None:
        pkg = self.packages.get(package_id)
        if pkg:
            pkg["status"] = status
            if completed:
                pkg["completed_at"] = "2026-06-15T00:00:05+00:00"

    async def create_sections(self, package_id, project_id, sections) -> int:
        self.sections[package_id] = [
            {
                "section_key": s.section_key,
                "title": s.title,
                "content": dict(s.content),
                "content_summary": s.content_summary,
                "order_index": s.order_index,
                "status": s.status,
            }
            for s in sections
        ]
        return len(sections)

    async def create_artifacts(self, package_id, project_id, artifacts) -> int:
        self.artifacts[package_id] = [
            {
                "artifact_type": a.artifact_type,
                "source_table": a.source_table,
                "source_id": a.source_id,
                "title": a.title,
                "uri": a.uri,
                "content": a.content,
            }
            for a in artifacts
        ]
        return len(artifacts)

    async def create_acceptance_gate_run(self, package_id, project_id, pilot_id, gate) -> str:
        gid = _id()
        self.gate_runs[package_id] = {
            "id": gid,
            "gate_key": gate.gate_key,
            "gate_type": gate.gate_type,
            "status": gate.status,
            "decision": gate.decision,
            "human_review_required": gate.human_review_required,
            "human_review_status": gate.human_review_status,
            "blocking_findings_count": gate.blocking_findings_count,
            "total_checks": gate.total_checks,
            "passed_checks": gate.passed_checks,
            "failed_checks": gate.failed_checks,
            "warning_checks": gate.warning_checks,
            "created_at": "2026-06-15T00:00:03+00:00",
            "completed_at": "2026-06-15T00:00:03+00:00",
        }
        return gid

    async def create_gate_check_results(self, gate_run_id, package_id, project_id, checks) -> int:
        self.gate_checks[package_id] = [
            {
                "check_key": c.check_key,
                "check_type": c.check_type,
                "status": c.status,
                "severity": c.severity,
                "blocking": c.blocking,
                "evidence_ref": dict(c.evidence_ref),
                "summary": c.summary,
            }
            for c in checks
        ]
        return len(checks)

    async def create_operator_review_placeholder(
        self, package_id, project_id, gate_run_id, review
    ) -> str:
        rid = _id()
        self.operator_reviews[package_id] = {
            "id": rid,
            "reviewer": review.reviewer,
            "review_status": review.review_status,
            "review_summary": review.review_summary,
            "requested_changes": list(review.requested_changes),
            "reviewed_at": None,
            "created_at": "2026-06-15T00:00:04+00:00",
        }
        return rid

    async def create_handoff_summaries(self, package_id, project_id, summaries) -> list:
        ids = []
        self.handoffs[package_id] = []
        for h in summaries:
            hid = _id()
            ids.append(hid)
            self.handoffs[package_id].append(
                {
                    "summary_type": h.summary_type,
                    "title": h.title,
                    "summary": h.summary,
                    "highlights": list(h.highlights),
                    "limitations": list(h.limitations),
                    "next_steps": list(h.next_steps),
                    "artifact_refs": list(h.artifact_refs),
                    "created_by_agent": h.created_by_agent,
                }
            )
        return ids

    async def create_readiness_snapshot(self, package_id, project_id, pilot_id, snapshot) -> str:
        sid = _id()
        self.readiness[package_id] = {
            "readiness_status": snapshot.readiness_status,
            "project_ready": snapshot.project_ready,
            "design_ready": snapshot.design_ready,
            "workspace_ready": snapshot.workspace_ready,
            "qa_ready": snapshot.qa_ready,
            "acceptance_ready": snapshot.acceptance_ready,
            "safety_ready": snapshot.safety_ready,
            "docs_ready": snapshot.docs_ready,
            "human_acceptance_pending": snapshot.human_acceptance_pending,
            "blocking_reasons": list(snapshot.blocking_reasons),
            "warnings": list(snapshot.warnings),
            "created_at": "2026-06-15T00:00:04+00:00",
        }
        return sid

    async def set_package_report(self, package_id, report) -> None:
        self.reports[package_id] = dict(report)
        pkg = self.packages.get(package_id)
        if pkg:
            pkg.setdefault("metadata", {})["report"] = dict(report)

    async def set_export_metadata(self, package_id, export_metadata) -> None:
        self.export_metadata[package_id] = dict(export_metadata)
        pkg = self.packages.get(package_id)
        if pkg:
            pkg.setdefault("metadata", {})["export_metadata"] = dict(export_metadata)

    # ---- reads ----
    async def get_delivery_package(self, package_id):
        return self.packages.get(package_id)

    async def list_delivery_packages(self, *, project_id=None, limit=100):
        rows = [self.packages[p] for p in self._order]
        if project_id:
            rows = [r for r in rows if r["project_id"] == project_id]
        return rows[:limit]

    async def get_latest_package(self, project_id=None):
        rows = await self.list_delivery_packages(project_id=project_id, limit=1)
        return rows[0] if rows else None

    async def get_package_sections(self, package_id):
        return self.sections.get(package_id, [])

    async def get_package_artifacts(self, package_id):
        return self.artifacts.get(package_id, [])

    async def get_acceptance_gate(self, package_id):
        return self.gate_runs.get(package_id)

    async def get_gate_check_results(self, package_id):
        return self.gate_checks.get(package_id, [])

    async def get_handoff_summaries(self, package_id):
        return self.handoffs.get(package_id, [])

    async def get_readiness_snapshot(self, package_id):
        return self.readiness.get(package_id)

    async def get_operator_review(self, package_id):
        return self.operator_reviews.get(package_id)

    async def get_delivery_package_report(self, package_id):
        return self.reports.get(package_id)
