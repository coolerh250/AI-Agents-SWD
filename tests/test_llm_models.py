"""Stage 30 — LLM dataclass / schema tests."""

from __future__ import annotations

from shared.sdk.llm import (
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMPatchProposal,
    LLMTestPlan,
)


def test_development_plan_clamps_confidence_below_zero() -> None:
    p = LLMDevelopmentPlan(task_id="t1", confidence=-5.0)
    assert p.confidence == 0.0
    assert p.requires_human_review is True


def test_development_plan_clamps_confidence_above_one() -> None:
    p = LLMDevelopmentPlan(task_id="t1", confidence=42.0)
    assert p.confidence == 1.0


def test_development_plan_requires_human_review_overridden_true() -> None:
    p = LLMDevelopmentPlan(task_id="t1", confidence=0.9, requires_human_review=False)
    # Stage 30 unconditionally enforces human review.
    assert p.requires_human_review is True


def test_patch_proposal_proposed_files_populates_from_changes() -> None:
    p = LLMPatchProposal(
        task_id="t1",
        changes=[
            LLMFileChange(file_path="docs/generated/x.md", change_type="create"),
            LLMFileChange(file_path="docs/generated/y.md", change_type="update"),
        ],
    )
    assert p.proposed_files == ["docs/generated/x.md", "docs/generated/y.md"]
    assert p.requires_human_review is True


def test_patch_proposal_requires_human_review_always_true() -> None:
    p = LLMPatchProposal(task_id="t1", requires_human_review=False)
    assert p.requires_human_review is True


def test_test_plan_to_dict_roundtrip() -> None:
    p = LLMTestPlan(task_id="t1", unit_tests=["test_x"], risks=["low"])
    d = p.to_dict()
    assert d["task_id"] == "t1"
    assert d["unit_tests"] == ["test_x"]
    assert d["risks"] == ["low"]


def test_file_change_change_type_round_trips() -> None:
    c = LLMFileChange(file_path="docs/generated/x.md", change_type="create")
    d = c.to_dict()
    assert d["change_type"] == "create"
    assert d["file_path"] == "docs/generated/x.md"


def test_to_dict_does_not_leak_internal_state() -> None:
    p = LLMPatchProposal(
        task_id="t1",
        proposed_files=["docs/generated/x.md"],
        changes=[LLMFileChange(file_path="docs/generated/x.md", change_type="create")],
        rationale="x",
        risk_level="low",
    )
    d = p.to_dict()
    # Spot check the keys we promise.
    for key in (
        "task_id",
        "patch_id",
        "proposed_files",
        "changes",
        "rationale",
        "risk_level",
        "confidence",
        "requires_human_review",
    ):
        assert key in d
