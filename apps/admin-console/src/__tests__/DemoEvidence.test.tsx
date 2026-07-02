import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DemoEvidence } from "../pages/DemoEvidence";

afterEach(() => vi.restoreAllMocks());

// Combined body: every fetched endpoint returns this superset; each section reads its key.
const BODY = {
  projects: [
    {
      project_id: "p1",
      project_key: "PRJ-SAAS-USER-MANAGEMENT-MODULE",
      name: "SaaS User Management Module",
      status: "active",
      environment_scope: "nonprod",
      production_allowed: false,
    },
  ],
  work_items: [
    {
      work_item_key: "WI-0001",
      id: "w1",
      title: "Create user CRUD API",
      lifecycle_state: "created",
      production_effect: false,
    },
  ],
  executions: [{ agent: "intake-agent", status: "completed", task_id: "demo-crud-userapi" }],
  workflows: [
    {
      task_id: "demo-crud-userapi",
      stage: "completed",
      approval_status: "not_required",
      risk_level: "low",
      production_executed: false,
    },
  ],
  count: 2,
  validation_runs: [],
  workspaces: [
    { workspace_id: "ws1", task_id: "demo-crud-userapi", status: "completed", execution_mode: "mock" },
  ],
  events: [
    {
      event_type: "work_item_created",
      from_state: null,
      to_state: "created",
      actor: "staging-demo",
      role: "intake",
    },
  ],
  production_executed_true_count: 0,
};

describe("DemoEvidence", () => {
  it("renders the five demo-evidence sections with data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => BODY }),
    );
    render(
      <MemoryRouter>
        <DemoEvidence />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Demo Evidence")).toBeDefined());
    // WI-0001 identity
    expect(screen.getByText("Create user CRUD API")).toBeDefined();
    expect(screen.getByText("WI-0001")).toBeDefined();
    // agent executions
    expect(screen.getByText("intake-agent")).toBeDefined();
    // audit evidence
    expect(screen.getByText("work_item_created")).toBeDefined();
    // safety posture (production_executed_true_count value rendered)
    expect(screen.getByText("Safety Posture")).toBeDefined();
  });
});
