"""Stage 30 — deterministic mock LLM provider.

The mock never calls the network. It inspects the input description /
request_type / task_id and produces a stable response that:

1. Passes the safety policy when the task is well-formed.
2. Deliberately triggers a policy block when the description contains
   the words ``denied``, ``deletion``, ``destructive``, or
   ``secret-token`` so verify scripts can exercise the block path.
3. Always sets ``requires_human_review=True``.
4. Always reports zero tokens / zero cost.

The behaviour is deterministic on ``task_id`` so the same task always
yields the same response — making tests + audit events stable.
"""

from __future__ import annotations

import hashlib
from typing import Any

from shared.sdk.llm.models import (
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMPatchProposal,
    LLMTestPlan,
)


def _short_hash(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def _classify_intent(description: str) -> str:
    text = (description or "").lower()
    if any(token in text for token in ("denied", "deletion", "destructive", "secret-token")):
        return "policy_trip"
    if any(token in text for token in ("doc", "readme", "documentation")):
        return "documentation"
    if any(token in text for token in ("api", "endpoint", "healthz", "service", "http", "fastapi")):
        return "demo_api"
    if any(token in text for token in ("utility", "helper", "function", "lib")):
        return "simple_utility"
    return "demo_api"


class MockLLMProvider:
    """In-process deterministic provider — never touches the network."""

    name = "mock"
    model_name = "mock-deterministic"

    def __init__(self, *, model_name: str | None = None) -> None:
        self.model_name = model_name or "mock-deterministic"

    # ------------------------------------------------------------------
    # development_plan
    # ------------------------------------------------------------------

    def generate_development_plan(
        self,
        *,
        task_id: str,
        description: str = "",
        request_type: str = "",
        execution_mode: str = "delivery_task",
        **_: Any,
    ) -> LLMDevelopmentPlan:
        intent = _classify_intent(description)
        files = self._files_for(intent, task_id)
        steps = [
            "Inspect the existing controlled-generator template before proposing edits",
            "Limit changes to the allowlisted paths under docs/generated/, "
            "apps/demo-generated/, tests/generated/",
            "Add tests under tests/generated/ that exercise the new code path",
            "Document the change under docs/generated/ if relevant",
        ]
        return LLMDevelopmentPlan(
            task_id=task_id,
            summary=(
                f"[mock] {intent} plan for {task_id} "
                "— no real LLM, no network call, requires human review."
            ),
            files_to_consider=files,
            proposed_steps=steps,
            assumptions=[
                "controlled deterministic generator handles the actual file write",
                "no real LLM API was contacted",
                f"execution_mode={execution_mode}",
                f"request_type={request_type or 'unknown'}",
            ],
            questions=[
                "Is the proposed file list aligned with the task's acceptance criteria?",
                "Should the existing deterministic template suffice instead?",
            ],
            risks=[
                "low — mock provider, deterministic output, no execution",
            ],
            test_strategy=(
                "pytest tests/generated/ + ./scripts/run_tests.sh; "
                "verify_llm_assisted_development.sh covers the proposal flow."
            ),
            confidence=0.8 if intent != "policy_trip" else 0.2,
            requires_human_review=True,
        )

    # ------------------------------------------------------------------
    # patch_proposal
    # ------------------------------------------------------------------

    def generate_patch_proposal(
        self,
        *,
        task_id: str,
        description: str = "",
        request_type: str = "",
        execution_mode: str = "delivery_task",
        **_: Any,
    ) -> LLMPatchProposal:
        intent = _classify_intent(description)
        patch_id = f"mock-{_short_hash(task_id, intent)}"
        if intent == "policy_trip":
            return self._policy_trip_proposal(task_id, patch_id, description)
        changes = self._changes_for(intent, task_id)
        return LLMPatchProposal(
            task_id=task_id,
            patch_id=patch_id,
            proposed_files=[c.file_path for c in changes],
            changes=changes,
            rationale=(
                f"[mock] deterministic {intent} proposal for {task_id}. "
                "Only allowlisted paths under docs/generated/, "
                "apps/demo-generated/, tests/generated/."
            ),
            risk_level="low" if intent != "demo_api" else "medium",
            safety_notes=[
                "no real LLM call",
                "no production deploy",
                "no real GitHub write",
                "requires human review before workspace accept",
            ],
            test_commands=[
                "./scripts/run_tests.sh",
                "./scripts/verify_llm_assisted_development.sh",
            ],
            rollback_plan=(
                "Revert the proposed workspace files manually — proposals "
                "are not committed automatically."
            ),
            confidence=0.8,
            requires_human_review=True,
        )

    def _policy_trip_proposal(
        self, task_id: str, patch_id: str, description: str
    ) -> LLMPatchProposal:
        """Construct a proposal that the policy will refuse.

        ``policy_trip`` is the verify-script entry point. Depending on
        which trigger word the operator put in the description, we
        emit a violation that hits one of the policy rules without
        ever writing a real secret to disk.
        """
        text = (description or "").lower()
        if "denied" in text:
            change = LLMFileChange(
                file_path="infra/docker-compose/docker-compose.yml",
                change_type="update",
                proposed_content="services: {}\n",
                diff_summary="touch denylisted infra file",
                reason="policy_trip:denied_path",
            )
        elif "deletion" in text:
            change = LLMFileChange(
                file_path="docs/generated/oops.md",
                change_type="delete",
                proposed_content="",
                diff_summary="attempt delete",
                reason="policy_trip:deletion",
            )
        elif "secret-token" in text:
            change = LLMFileChange(
                file_path="docs/generated/oops.md",
                change_type="create",
                # Synthetic non-secret marker — matches the placeholder
                # regex (``ghp_`` + 20+ chars) without containing a real
                # token. Safe by design.
                proposed_content="token = ghp_" + ("A" * 40) + "\n",
                diff_summary="embed a fake secret-like literal",
                reason="policy_trip:secret-token",
            )
        else:  # destructive
            change = LLMFileChange(
                file_path="apps/demo-generated/wipe.py",
                change_type="create",
                proposed_content="import os\nos.system('rm -rf /')\n",
                diff_summary="destructive command",
                reason="policy_trip:destructive",
            )
        return LLMPatchProposal(
            task_id=task_id,
            patch_id=patch_id,
            proposed_files=[change.file_path],
            changes=[change],
            rationale="[mock] policy-trip proposal — must be refused by safety policy",
            risk_level="high",
            safety_notes=["policy_trip", "must be blocked"],
            test_commands=[],
            rollback_plan="no rollback — proposal must be refused",
            confidence=0.3,
            requires_human_review=True,
        )

    # ------------------------------------------------------------------
    # test_plan
    # ------------------------------------------------------------------

    def generate_test_plan(
        self,
        *,
        task_id: str,
        description: str = "",
        **_: Any,
    ) -> LLMTestPlan:
        return LLMTestPlan(
            task_id=task_id,
            unit_tests=[
                "tests/generated/test_<feature>.py — happy path",
                "tests/generated/test_<feature>.py — error path",
            ],
            integration_tests=[
                "./scripts/run_tests.sh",
            ],
            manual_tests=[
                "Inspect /operations/llm/proposals/{task_id} and review the "
                "patch before merging.",
            ],
            acceptance_checks=[
                "Workspace files match the proposal",
                "QA gate passes",
                "No real GitHub write",
            ],
            risks=[
                "low — mock provider deterministic output",
            ],
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _files_for(intent: str, task_id: str) -> list[str]:
        if intent == "documentation":
            return [f"docs/generated/{task_id}.md"]
        if intent == "simple_utility":
            return [
                f"apps/demo-generated/{task_id}_utility.py",
                f"tests/generated/test_{task_id}_utility.py",
            ]
        if intent == "policy_trip":
            return ["infra/docker-compose/docker-compose.yml"]
        # demo_api default
        return [
            f"apps/demo-generated/{task_id}_api.py",
            f"tests/generated/test_{task_id}_api.py",
        ]

    @staticmethod
    def _changes_for(intent: str, task_id: str) -> list[LLMFileChange]:
        if intent == "documentation":
            return [
                LLMFileChange(
                    file_path=f"docs/generated/{task_id}.md",
                    change_type="create",
                    proposed_content=(
                        f"# {task_id}\n\nDocumentation generated by the mock LLM "
                        "provider. Human review required.\n"
                    ),
                    diff_summary="add generated documentation page",
                    reason="documentation intent",
                )
            ]
        if intent == "simple_utility":
            return [
                LLMFileChange(
                    file_path=f"apps/demo-generated/{task_id}_utility.py",
                    change_type="create",
                    proposed_content=("def add(a: int, b: int) -> int:\n    return a + b\n"),
                    diff_summary="add deterministic utility",
                    reason="simple utility intent",
                ),
                LLMFileChange(
                    file_path=f"tests/generated/test_{task_id}_utility.py",
                    change_type="create",
                    proposed_content=(
                        f"from apps.demo_generated.{task_id}_utility import add\n\n\n"
                        "def test_add() -> None:\n    assert add(1, 2) == 3\n"
                    ),
                    diff_summary="add utility test",
                    reason="test scaffolding",
                ),
            ]
        # demo_api default
        return [
            LLMFileChange(
                file_path=f"apps/demo-generated/{task_id}_api.py",
                change_type="create",
                proposed_content=(
                    "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n"
                    "@app.get('/healthz')\ndef healthz() -> dict:\n"
                    "    return {'status': 'ok'}\n"
                ),
                diff_summary="add /healthz endpoint",
                reason="demo_api intent",
            ),
            LLMFileChange(
                file_path=f"tests/generated/test_{task_id}_api.py",
                change_type="create",
                proposed_content=(
                    "from fastapi.testclient import TestClient\n"
                    f"from apps.demo_generated.{task_id}_api import app\n\n\n"
                    "def test_healthz() -> None:\n"
                    "    client = TestClient(app)\n"
                    "    response = client.get('/healthz')\n"
                    "    assert response.status_code == 200\n"
                    "    assert response.json()['status'] == 'ok'\n"
                ),
                diff_summary="add /healthz test",
                reason="test scaffolding",
            ),
        ]
