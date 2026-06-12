"""Stage 40 -- postmortem structural tests."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_postmortem_store_has_required_methods():
    import inspect

    from shared.sdk.incidents.postmortem import PostmortemStore

    methods = [name for name, _ in inspect.getmembers(PostmortemStore, predicate=inspect.isfunction)]
    assert "create_postmortem" in methods
    assert "get_postmortem" in methods
    assert "list_postmortems" in methods
    assert "count_required" in methods


def test_postmortem_status_constants():
    from shared.sdk.incidents.postmortem import (
        STATUS_CANCELLED,
        STATUS_COMPLETED,
        STATUS_DRAFT,
        STATUS_IN_REVIEW,
    )

    assert STATUS_DRAFT == "draft"
    assert STATUS_IN_REVIEW == "in_review"
    assert STATUS_COMPLETED == "completed"
    assert STATUS_CANCELLED == "cancelled"


def test_sev1_requires_postmortem():
    from shared.sdk.incidents.severity import SEV1_CRITICAL, SEV2_HIGH, postmortem_required

    assert postmortem_required(SEV1_CRITICAL) is True
    assert postmortem_required(SEV2_HIGH) is True


def test_postmortem_operation_in_operations():
    src = (_REPO_ROOT / "apps" / "orchestrator" / "src" / "operations.py").read_text(
        encoding="utf-8"
    )
    assert "PostmortemStore" in src
    assert "postmortem" in src
