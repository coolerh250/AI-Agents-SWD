"""Stage 46 -- security reviewer tests."""

from __future__ import annotations

from design_review_fakes import build_fastapi_todo_context

from shared.sdk.design_review.models import ReviewContext
from shared.sdk.design_review.security_reviewer import review_security


def test_fastapi_todo_security_only_low() -> None:
    findings = review_security(build_fastapi_todo_context())
    # auth is non-scope -> accepted low; input validation low; no high/critical
    assert findings
    assert all(f.severity in ("low", "medium") for f in findings)
    assert not any(f.severity in ("high", "critical") for f in findings)


def test_auth_flagged_as_accepted_non_scope() -> None:
    findings = review_security(build_fastapi_todo_context())
    auth = [f for f in findings if f.finding_key == "SEC-AUTH-NONSCOPE"]
    assert auth and auth[0].status == "accepted"


def test_production_in_scope_flags_high() -> None:
    ctx = ReviewContext(
        project_id="p",
        brief={"scope": ["production deploy the service"], "non_scope": []},
    )
    findings = review_security(ctx)
    assert any(f.finding_key == "SEC-PROD-IN-SCOPE" and f.severity == "high" for f in findings)
