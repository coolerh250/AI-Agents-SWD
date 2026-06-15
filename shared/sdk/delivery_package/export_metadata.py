"""Stage 49 -- exportable delivery package metadata.

Produces a compact, redacted JSON/Markdown metadata payload describing the
package for Admin Console v0. Controlled-only: this stage does NOT build a
PDF/DOCX, does NOT send the package anywhere, and does NOT commit export
artifacts. No secrets, no chain-of-thought, no raw code.
"""

from __future__ import annotations


def build_export_metadata(
    *,
    package: dict,
    gate: dict | None,
    readiness: dict | None,
    sections: list,
    handoff_summaries: list,
) -> dict:
    """Return the export metadata dict (safe to persist / surface via API)."""
    return {
        "export_format": "json",
        "exportable": True,
        "external_delivery_performed": False,
        "package_id": package.get("id"),
        "package_key": package.get("package_key"),
        "package_type": package.get("package_type"),
        "package_status": package.get("status"),
        "project_id": package.get("project_id"),
        "pilot_id": package.get("pilot_id"),
        "human_acceptance_status": package.get("human_acceptance_status", "pending"),
        "acceptance_gate_status": (gate or {}).get("status"),
        "acceptance_gate_decision": (gate or {}).get("decision"),
        "readiness_status": (readiness or {}).get("readiness_status"),
        "section_keys": [getattr(s, "section_key", None) for s in sections],
        "sections_ready_count": sum(1 for s in sections if getattr(s, "status", None) == "ready"),
        "sections_missing_count": sum(
            1 for s in sections if getattr(s, "status", None) == "missing"
        ),
        "handoff_summary_types": [getattr(h, "summary_type", None) for h in handoff_summaries],
        "controlled_only": True,
        "production_executed": False,
    }


def render_markdown(metadata: dict) -> str:
    """Render a tiny Markdown view of the export metadata (no secrets)."""
    lines = [
        f"# Delivery Package {metadata.get('package_key', '')}",
        "",
        f"- Type: {metadata.get('package_type')}",
        f"- Status: {metadata.get('package_status')}",
        f"- Acceptance gate: {metadata.get('acceptance_gate_status')} "
        f"({metadata.get('acceptance_gate_decision')})",
        f"- Readiness: {metadata.get('readiness_status')}",
        f"- Human acceptance: {metadata.get('human_acceptance_status')}",
        f"- Sections ready: {metadata.get('sections_ready_count')} / "
        f"missing: {metadata.get('sections_missing_count')}",
        "- Controlled-only: true; production_executed: false",
    ]
    return "\n".join(lines)


__all__ = ["build_export_metadata", "render_markdown"]
