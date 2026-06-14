"""Stage 46 -- security risk review (deterministic, no real scan)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext

_SCOPE_CREEP_TERMS = ("auth", "authentication", "login", "oauth", "frontend", "ui", "multi-user")


def review_security(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    brief = ctx.brief or {}
    non_scope = " ".join(str(s) for s in brief.get("non_scope", [])).lower()
    scope = " ".join(str(s) for s in brief.get("scope", [])).lower()
    constraints = " ".join(str(s) for s in brief.get("constraints", [])).lower()
    assumptions = " ".join(str(s) for s in brief.get("assumptions", [])).lower()

    # No secrets required -- accepted posture (low informational finding).
    if "secret" not in (constraints + assumptions + non_scope):
        findings.append(
            DesignReviewFinding(
                finding_key="SEC-NO-SECRET-DECL",
                finding_type="security_risk",
                severity="low",
                title="No explicit 'no secrets required' declaration",
                description="The brief does not explicitly declare that no secrets are required.",
                recommendation="State the no-secret posture explicitly.",
                created_by_agent="security-capability",
            )
        )
    # Production deployment must be out of scope.
    if "production" in scope and "deploy" in scope:
        findings.append(
            DesignReviewFinding(
                finding_key="SEC-PROD-IN-SCOPE",
                finding_type="security_risk",
                severity="high",
                title="Production deployment appears in scope",
                description="Production deployment is in scope; this stage is planning-only.",
                recommendation="Move production deployment to non-scope.",
                created_by_agent="security-capability",
            )
        )
    # Auth scope creep -> accepted non-scope if declared, else low risk.
    if any(t in scope for t in _SCOPE_CREEP_TERMS):
        findings.append(
            DesignReviewFinding(
                finding_key="SEC-SCOPE-CREEP",
                finding_type="scope_risk",
                severity="medium",
                title="Auth/frontend in scope",
                description="Auth or frontend appears in scope, expanding the security surface.",
                recommendation="Confirm whether auth/frontend is intended; otherwise non-scope.",
                created_by_agent="security-capability",
            )
        )
    else:
        findings.append(
            DesignReviewFinding(
                finding_key="SEC-AUTH-NONSCOPE",
                finding_type="security_risk",
                severity="low",
                title="Lack of auth (accepted non-scope)",
                description="The service has no authentication; accepted as non-scope for "
                "a local-only dev service.",
                recommendation="Add auth before any multi-user or production use.",
                status="accepted",
                created_by_agent="security-capability",
            )
        )
    # Input validation residual risk (low/medium).
    findings.append(
        DesignReviewFinding(
            finding_key="SEC-INPUT-VALIDATION",
            finding_type="security_risk",
            severity="low",
            title="Input validation residual risk",
            description="CRUD inputs should be validated; covered by tests, low residual risk.",
            recommendation="Add validation + negative tests.",
            created_by_agent="security-capability",
        )
    )
    return findings


__all__ = ["review_security"]
