"""Step AT-M3.6B.1 -- the two PRE-M3.6B bounds, and proof they do not invalidate history.

AT-D23 section 6 carried two items as PRE-M3.6B backlog: the reasoning artifact had no size bound
and ``PlanContent`` had no global step-count bound. Both were tolerable while every artifact was
authored by a deterministic in-process mock. This slice is what makes them load-bearing, so this is
where they close.

The compatibility half matters as much as the bounds. A new limit that makes stored history
unreadable does not protect the product, it destroys the evidence the product is made of -- so the
bound is application-level on NEW plans, no database constraint is added, and this module goes
looking for a canonical row that would now fail to load.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from shared.sdk.agent_planning.models import (
    MAX_PLAN_STEPS,
    MAX_STEP_CAPABILITIES,
    MAX_STEP_CONSTRAINTS,
    MAX_STEP_DEPENDENCIES,
    MAX_STEP_EXPECTED_OUTPUTS,
    PlanContent,
    PlanStep,
)
from shared.sdk.agent_reasoning.models import (
    MAX_ARTIFACT_BYTES,
    PlanDraftArtifact,
    ProposalArtifact,
    artifact_payload_size,
    assert_artifact_within_size,
)

ROOT = Path(__file__).resolve().parents[1]


class TestPlanBounds:
    def test_the_approved_limits(self) -> None:
        assert MAX_PLAN_STEPS == 40
        assert MAX_STEP_DEPENDENCIES == 10
        assert MAX_STEP_CAPABILITIES == 10
        assert MAX_STEP_EXPECTED_OUTPUTS == 10
        assert MAX_STEP_CONSTRAINTS == 10

    def test_forty_steps_is_the_boundary(self) -> None:
        steps = tuple(PlanStep(step_key=f"s{i}", title="t") for i in range(MAX_PLAN_STEPS))
        assert len(PlanContent(objective="o", steps=steps).steps) == MAX_PLAN_STEPS
        with pytest.raises(Exception):
            PlanContent(
                objective="o",
                steps=steps + (PlanStep(step_key="overflow", title="t"),),
            )

    @pytest.mark.parametrize(
        "field,limit",
        [
            ("depends_on", MAX_STEP_DEPENDENCIES),
            ("required_capabilities", MAX_STEP_CAPABILITIES),
            ("expected_outputs", MAX_STEP_EXPECTED_OUTPUTS),
            ("constraints", MAX_STEP_CONSTRAINTS),
        ],
    )
    def test_each_per_step_list_has_a_boundary(self, field: str, limit: int) -> None:
        at_limit = tuple(f"v{i}" for i in range(limit))
        assert len(getattr(PlanStep(step_key="a", title="t", **{field: at_limit}), field)) == limit
        with pytest.raises(Exception):
            PlanStep(step_key="a", title="t", **{field: at_limit + ("one-too-many",)})

    def test_the_bound_caps_the_graph_not_only_the_list(self) -> None:
        """Edges, not steps, are what M3.5 walks -- so the edge count is the number that matters."""
        assert MAX_PLAN_STEPS * MAX_STEP_DEPENDENCIES == 400

    def test_existing_structural_validation_still_applies(self) -> None:
        """The new bounds are additive. Uniqueness, existence and self-dependency are unchanged."""
        with pytest.raises(Exception):
            PlanContent(
                objective="o",
                steps=(PlanStep(step_key="a", title="t"), PlanStep(step_key="a", title="t")),
            )
        with pytest.raises(Exception):
            PlanContent(
                objective="o", steps=(PlanStep(step_key="a", title="t", depends_on=("b",)),)
            )
        with pytest.raises(Exception):
            PlanContent(
                objective="o", steps=(PlanStep(step_key="a", title="t", depends_on=("a",)),)
            )


class TestArtifactSizeBound:
    def test_the_approved_limit(self) -> None:
        assert MAX_ARTIFACT_BYTES == 256 * 1024

    def test_an_ordinary_artifact_is_orders_of_magnitude_below_it(self) -> None:
        artifact = ProposalArtifact(
            summary="s" * 2000,
            rationale_summary="r" * 2000,
            recommendation="x" * 1000,
        )
        assert artifact_payload_size(artifact.as_safe_dict()) < MAX_ARTIFACT_BYTES // 20

    def test_a_maximal_plan_artifact_still_fits(self) -> None:
        """The bound must not refuse the largest plan the schema now admits, or the two limits
        would contradict each other and no live decompose_plan could ever succeed."""
        steps = tuple(
            PlanStep(
                step_key=f"step-{i}",
                title="t" * 300,
                depends_on=tuple(f"step-{j}" for j in range(min(i, MAX_STEP_DEPENDENCIES))),
                required_capabilities=tuple(f"cap-{j}" for j in range(MAX_STEP_CAPABILITIES)),
                expected_outputs=tuple(f"out-{j}" for j in range(MAX_STEP_EXPECTED_OUTPUTS)),
            )
            for i in range(MAX_PLAN_STEPS)
        )
        artifact = PlanDraftArtifact(
            summary="s",
            rationale_summary="r",
            plan=PlanContent(objective="o", steps=steps),
        )
        assert_artifact_within_size(artifact.as_safe_dict())

    def test_the_backstop_catches_what_the_step_bound_cannot(self) -> None:
        """``PlanContent.constraints`` is bounded neither in count nor in item length, so a plan can
        be schema-valid and still be enormous. That is why the byte bound is independent."""
        artifact = PlanDraftArtifact(
            summary="s",
            rationale_summary="r",
            plan=PlanContent(objective="o", constraints=("x" * (MAX_ARTIFACT_BYTES + 1),)),
        )
        with pytest.raises(ValueError, match="exceeds the durable maximum"):
            assert_artifact_within_size(artifact.as_safe_dict())

    def test_the_measurement_is_deterministic(self) -> None:
        payload = {"b": 2, "a": 1, "c": {"z": 1, "y": 2}}
        assert artifact_payload_size(payload) == artifact_payload_size(
            {"c": {"y": 2, "z": 1}, "a": 1, "b": 2}
        )


class TestHistoricalCompatibility:
    """AT-M3.6B.1 section 57: a new bound must not make canonical history unreadable."""

    def test_no_committed_json_or_sql_fixture_holds_an_over_bound_plan(self) -> None:
        offenders: list[str] = []
        for path in list(ROOT.glob("**/*.json")) + list(ROOT.glob("**/*.sql")):
            parts = set(path.parts)
            if parts & {".git", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # The JSON-quoted form. A bare ``step_key`` is a COLUMN NAME -- migrations 020, 042 and
            # 043 all mention one in DDL or in a comment -- and a schema that names the field is not
            # a stored plan. Only a serialized payload can violate a bound.
            if '"step_key"' not in text:
                continue
            offenders.append(str(path.relative_to(ROOT)))
        # Nothing in the repository stores a plan as committed data: plans exist only as runtime
        # rows (scanned below) and as Python fixtures, and the fixtures are exercised by the
        # AT-M3.2/3.4/3.5/3.6A regression suites, which would fail outright if one exceeded the new
        # bounds.
        assert offenders == [], offenders

    @pytest.mark.asyncio
    async def test_no_stored_plan_revision_violates_the_new_bounds(self) -> None:
        """Load every persisted plan through the bounded model. A canonical row that no longer
        parses would be a DESIGN_REVIEW_REQUIRED stop condition, not something to work around."""
        asyncpg = pytest.importorskip("asyncpg")
        dsn = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
        try:
            conn = await asyncpg.connect(dsn=dsn, timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping stored-plan compatibility scan")
        try:
            exists = await conn.fetchval("SELECT to_regclass('public.plan_revisions')")
            if exists is None:
                pytest.skip("plan_revisions is not present; skipping stored-plan scan")
            rows = await conn.fetch("SELECT plan_revision_id, plan FROM plan_revisions")
        finally:
            await conn.close()

        violations: list[str] = []
        for row in rows:
            raw = row["plan"]
            payload = json.loads(raw) if isinstance(raw, str) else raw
            try:
                PlanContent.model_validate(payload)
            except Exception as exc:
                violations.append(f"{row['plan_revision_id']}: {type(exc).__name__}")
        assert violations == [], violations
