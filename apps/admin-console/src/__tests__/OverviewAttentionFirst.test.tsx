import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import {
  agentExecutionStatusLabel,
  ExecutiveOverview,
} from "../pages/ExecutiveOverview";
import type { Task, TaskStatus } from "../tasks/taskTypes";

const OVERVIEW = {
  active_projects_count: 2,
  projects_count: 2,
  delivery_packages_count: 3,
  ready_for_review_packages_count: 1,
  latest_mini_delivery_pilot_status: "completed",
  latest_delivery_package_status: "ready_for_review",
  latest_acceptance_gate_decision: "ready_for_operator_review",
  latest_acceptance_gate_status: "pending",
  latest_human_acceptance_status: "pending",
  safety_result: "safe",
  production_executed_true_count: 0,
  delivery_package_ready_for_admin_console: true,
  latest_full_regression_status: "passed",
  backup_readiness_gaps: [],
  backup_production_ready: false,
  incidents_summary: {},
  llm_summary: {},
  admin_console: {},
};

const SAFE_SAFETY = {
  production_executed_true_count: 0,
  workflow_production_executed_true_count: 0,
  task_api_workflow_dispatch_enabled: false,
  task_workroom_resume_dispatch_enabled: false,
  github_external_write_enabled: false,
  discord_external_send_enabled: false,
  llm_external_call_enabled: false,
  production_delegation_allowed: false,
  result: "safe",
};

function task(id: string, updatedAt: string, status: TaskStatus = "submitted"): Task {
  return {
    id,
    title: `Task ${id}`,
    status,
    updated_at: updatedAt,
    created_at: updatedAt,
  } as Task;
}

type AgentExecution = {
  id: string;
  agent: string;
  status?: string | null;
  completed_at?: string;
};

function installApi({
  tasks = [],
  executions = [],
}: {
  tasks?: Task[];
  executions?: AgentExecution[];
} = {}) {
  const fetchMock = vi.fn(async (input: unknown) => {
    const url = String(input);
    let body: unknown;
    if (url.includes("/operations/admin-console/overview")) {
      body = OVERVIEW;
    } else if (url.includes("/tasks?status=clarification_needed")) {
      const filtered = tasks.filter((item) => item.status === "clarification_needed");
      body = { count: filtered.length, tasks: filtered };
    } else if (url.includes("/tasks?status=blocked")) {
      const filtered = tasks.filter((item) => item.status === "blocked");
      body = { count: filtered.length, tasks: filtered };
    } else if (/\/tasks(?:$|\?)/.test(url)) {
      body = { count: tasks.length, tasks };
    } else if (url.includes("/operations/agent-executions")) {
      body = { count: executions.length, executions };
    } else if (url.includes("/operations/safety")) {
      body = SAFE_SAFETY;
    } else {
      throw new Error(`Unexpected request: ${url}`);
    }
    return { ok: true, status: 200, json: async () => body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderOverview() {
  render(
    <MemoryRouter>
      <ExecutiveOverview />
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("FE.1C attention-first Overview", () => {
  it("puts real attention counts above demoted existing metrics and uses status filters", async () => {
    const fetchMock = installApi({
      tasks: [
        task("decision", "2026-07-17T06:00:00Z", "clarification_needed"),
        task("blocked", "2026-07-17T05:00:00Z", "blocked"),
      ],
    });
    renderOverview();

    const attention = await screen.findByTestId("needs-attention");
    const metrics = screen.getByText("Platform & delivery metrics");
    expect(attention.compareDocumentPosition(metrics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(attention).getByText("agents waiting on your answer")).toBeDefined();
    expect(within(attention).getByText("waiting on an input")).toBeDefined();
    expect(screen.getByText("Active projects")).toBeDefined();

    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((url) => url.includes("status=clarification_needed"))).toBe(true);
    expect(urls.some((url) => url.includes("status=blocked"))).toBe(true);
  });

  it("shows exactly five current tasks sorted by updated_at descending", async () => {
    installApi({
      tasks: [
        task("oldest", "2026-07-11T00:00:00Z"),
        task("third", "2026-07-15T00:00:00Z"),
        task("newest", "2026-07-17T00:00:00Z"),
        task("fifth", "2026-07-13T00:00:00Z"),
        task("second", "2026-07-16T00:00:00Z"),
        task("fourth", "2026-07-14T00:00:00Z"),
      ],
    });
    renderOverview();

    const section = await screen.findByTestId("current-work");
    const links = within(section).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      expect.stringContaining("Task newest"),
      expect.stringContaining("Task second"),
      expect.stringContaining("Task third"),
      expect.stringContaining("Task fourth"),
      expect.stringContaining("Task fifth"),
    ]);
    expect(within(section).queryByText("Task oldest")).toBeNull();
  });

  it("uses calm empty states when tasks and agent runs are absent", async () => {
    installApi();
    renderOverview();

    expect(await screen.findByText("You're all caught up.")).toBeDefined();
    expect(screen.getByText("Nothing blocked.")).toBeDefined();
    expect(screen.getByText("No recent agent runs.")).toBeDefined();
    expect(screen.getByText("No tasks yet. Assign your first piece of work to the AI team.")).toBeDefined();
  });

  it("maps only observed contract statuses and falls back conservatively", async () => {
    installApi({
      executions: [
        { id: "1", agent: "Requirement Agent", status: "completed", completed_at: "2026-07-17T06:00:00Z" },
        { id: "2", agent: "QA Agent", status: "failed", completed_at: "2026-07-17T05:00:00Z" },
        { id: "3", agent: "Unknown Agent", status: "queued", completed_at: "2026-07-17T04:00:00Z" },
        { id: "4", agent: "Missing Agent", completed_at: "2026-07-17T03:00:00Z" },
      ],
    });
    renderOverview();

    const section = await screen.findByTestId("ai-team-activity");
    expect(within(section).getByText("Completed")).toBeDefined();
    expect(within(section).getByText("Needs review")).toBeDefined();
    expect(within(section).getAllByText("Not reported")).toHaveLength(2);
    expect(agentExecutionStatusLabel("running")).toBe("Not reported");
  });

  it("reuses the calibrated safety posture and points details to Safety Center", async () => {
    installApi();
    renderOverview();

    const section = await screen.findByTestId("system-posture");
    expect(within(section).getByText("Safe - no automated or production actions will run.")).toBeDefined();
    expect(within(section).queryByText("Evidence / details")).toBeNull();
    expect(within(section).getByRole("link", { name: "View Safety" }).getAttribute("href")).toBe("/safety");
  });

  it("keeps future capabilities as honest placeholders without fake counts or controls", async () => {
    installApi();
    renderOverview();

    const section = await screen.findByTestId("future-capabilities");
    expect(within(section).getByText(/Requires Step 66D/)).toBeDefined();
    expect(within(section).getByText(/Requires Step 66C\.4/)).toBeDefined();
    expect(within(section).getAllByText(/No workflow action available from this screen/)).toHaveLength(4);
    expect(within(section).queryAllByRole("button")).toHaveLength(0);
    expect(within(section).queryAllByRole("link")).toHaveLength(0);
    expect(within(section).queryByText(/^\d+$/)).toBeNull();
  });
});
