import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AgentExecutions } from "../pages/AgentExecutions";
import { QaCode } from "../pages/QaCode";
import { AuditEvidence } from "../pages/AuditEvidence";
import { TaskGraph } from "../pages/TaskGraph";
import { SafetyCenter } from "../pages/SafetyCenter";
import { MultiProjectDelivery } from "../pages/MultiProjectDelivery";
import { NAV_ITEMS } from "../components/Nav";

afterEach(() => vi.restoreAllMocks());

// Step 64E.4B -- every fetched endpoint returns this superset; each formal page
// reads its own key, mirroring the Step 64D staging demo evidence.
const BODY = {
  projects: [
    {
      project_id: "p1",
      project_key: "PRJ-SAAS-USER-MANAGEMENT-MODULE",
      name: "SaaS User Management Module",
      status: "active",
      environment_scope: "nonprod",
      production_allowed: false,
      registry_status: "registered",
    },
  ],
  work_items: [
    {
      work_item_key: "WI-0001",
      id: "w1",
      title: "Create user CRUD API",
      lifecycle_state: "created",
      production_effect: false,
      assigned_agent: "intake-agent",
    },
  ],
  delivery_state: "in_progress",
  executions: [
    { agent: "intake-agent", status: "completed", task_id: "demo-crud-userapi" },
    { agent: "development-agent", status: "completed", task_id: "demo-crud-userapi" },
  ],
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
  validation_runs: [{ task_id: "demo-crud-userapi", status: "completed", final_result: "passed" }],
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
  latest_pilot: { project: "SaaS User Management Module", status: "completed" },
  production_executed_true_count: 0,
  workflow_production_executed_true_count: 0,
  github_external_write_enabled: false,
  discord_external_send_enabled: false,
  llm_external_call_enabled: false,
  production_delegation_allowed: false,
  result: "warning",
};

function mockAll() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => BODY }),
  );
}

function renderPage(el: JSX.Element) {
  render(<MemoryRouter>{el}</MemoryRouter>);
}

describe("Product UI formal pages surface demo evidence", () => {
  it("Agent Executions renders the pipeline", async () => {
    mockAll();
    renderPage(<AgentExecutions />);
    await waitFor(() => expect(screen.getByText("Agent Executions")).toBeDefined());
    expect(screen.getByText("development-agent")).toBeDefined();
  });

  it("Workflows / Task Graph renders the workflow trace", async () => {
    mockAll();
    renderPage(<TaskGraph />);
    await waitFor(() => expect(screen.getByText("Workflows / Task Graph")).toBeDefined());
    expect(screen.getByText("demo-crud-userapi")).toBeDefined();
  });

  it("QA / Code renders QA runs and code workspaces", async () => {
    mockAll();
    renderPage(<QaCode />);
    await waitFor(() => expect(screen.getByText("QA / Code")).toBeDefined());
    expect(screen.getByText("ws1")).toBeDefined();
  });

  it("Audit / Evidence renders the work item events", async () => {
    mockAll();
    renderPage(<AuditEvidence />);
    await waitFor(() => expect(screen.getByText("Audit / Evidence")).toBeDefined());
    expect(screen.getByText("work_item_created")).toBeDefined();
  });

  it("Safety Center surfaces production_executed_true_count", async () => {
    mockAll();
    renderPage(<SafetyCenter />);
    await waitFor(() => expect(screen.getByText("Safety Center")).toBeDefined());
    expect(screen.getByText("production_executed_true_count")).toBeDefined();
  });

  it("Projects / Work Items auto-loads WI-0001 without a manual click", async () => {
    mockAll();
    renderPage(<MultiProjectDelivery />);
    await waitFor(() => expect(screen.getByText("Create user CRUD API")).toBeDefined());
  });
});

describe("Demo Evidence is diagnostic-only in navigation", () => {
  it("labels the demo-evidence nav entry as Diagnostics and lists it last", () => {
    const demo = NAV_ITEMS.find((i) => i.to === "/demo-evidence");
    expect(demo).toBeDefined();
    expect(demo?.label.toLowerCase()).toContain("diagnostic");
    expect(NAV_ITEMS[NAV_ITEMS.length - 1].to).toBe("/demo-evidence");
  });

  it("exposes the formal evidence pages in navigation", () => {
    const routes = NAV_ITEMS.map((i) => i.to);
    for (const r of ["/delivery", "/agent-executions", "/task-graph", "/qa-code", "/audit-evidence", "/safety"]) {
      expect(routes).toContain(r);
    }
  });
});
