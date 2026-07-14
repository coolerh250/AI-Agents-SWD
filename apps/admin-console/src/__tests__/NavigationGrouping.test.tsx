import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { App } from "../App";
import { Nav, NAV_GROUPS, NAV_ITEMS } from "../components/Nav";

const SAFETY_BODY = {
  production_executed_true_count: 0,
  workflow_production_executed_true_count: 0,
  github_external_write_enabled: false,
  discord_external_send_enabled: false,
  llm_external_call_enabled: false,
  production_delegation_allowed: false,
};

afterEach(() => vi.restoreAllMocks());

function mockSafety() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => SAFETY_BODY }),
  );
}

function renderNav(path = "/") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Nav />
    </MemoryRouter>,
  );
}

function renderApp(path: string) {
  mockSafety();
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function appSource() {
  return readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf-8");
}

function sourceFile(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf-8");
}

describe("Step 66UI.2-FE.1 navigation grouping", () => {
  it("renders the seven required navigation groups", () => {
    renderNav();

    expect(NAV_GROUPS.map((group) => group.label)).toEqual([
      "Overview",
      "Team Work",
      "Deliveries",
      "Operator Center",
      "Governance",
      "Platform Ops",
      "Settings",
    ]);

    for (const group of NAV_GROUPS) {
      expect(screen.getByTestId(`nav-group-${group.id}`)).toBeDefined();
      expect(screen.getByText(group.label)).toBeDefined();
    }
  });

  it("keeps task entry links and task detail/workroom routes", () => {
    renderNav();

    expect(screen.getByRole("link", { name: "Tasks" }).getAttribute("href")).toBe("/tasks");
    expect(screen.getByRole("link", { name: "Create Task" }).getAttribute("href")).toBe(
      "/tasks/new",
    );
    expect(appSource()).toContain('path="/tasks/:taskId/workroom"');
    expect(appSource()).toContain('path="/tasks/:taskId"');
  });

  it("groups Platform Ops and keeps its operational pages out of the first-level noise", () => {
    renderNav();

    const group = screen.getByTestId("nav-group-platform-ops");
    const toggle = within(group).getByRole("button", { name: /platform ops/i });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("link", { name: "Runtime Baseline" })).toBeNull();
    expect(NAV_ITEMS.some((item) => item.to === "/runtime")).toBe(true);
  });

  it("removes Demo Evidence from navigation but preserves its direct route", () => {
    renderNav();

    expect(screen.queryByText(/Demo Evidence/)).toBeNull();
    expect(NAV_ITEMS.some((item) => item.to === "/demo-evidence")).toBe(false);
    expect(appSource()).toContain('path="/demo-evidence"');
  });

  it("renders the 66D delivery placeholder without workflow actions", async () => {
    renderApp("/delivery-inbox");

    await waitFor(() => expect(screen.getByRole("heading", { name: "Delivery Inbox" })).toBeDefined());
    const panel = screen.getByTestId("placeholder-panel");
    expect(within(panel).getByText("Not yet available.")).toBeDefined();
    expect(within(panel).getByText("Requires Step 66D.")).toBeDefined();
    expect(within(panel).getByText("No workflow action available.")).toBeDefined();
    expect(within(panel).queryByRole("button")).toBeNull();
  });

  it("renders the 66C.4 reminder placeholder without workflow actions", async () => {
    renderApp("/clarification-reminders");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Reminder / Expiry" })).toBeDefined(),
    );
    const panel = screen.getByTestId("placeholder-panel");
    expect(within(panel).getByText("Requires Step 66C.4.")).toBeDefined();
    expect(within(panel).getByText("No workflow action available.")).toBeDefined();
    expect(within(panel).queryByRole("button")).toBeNull();
  });

  it("renders settings placeholders without fake controls", async () => {
    renderApp("/settings/roles-permissions");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Roles & Permissions" })).toBeDefined(),
    );
    const panel = screen.getByTestId("placeholder-panel");
    expect(within(panel).getByText("Requires Step 66S.")).toBeDefined();
    expect(within(panel).queryByRole("button")).toBeNull();
    expect(within(panel).queryByRole("link")).toBeNull();
  });

  it("does not introduce drag/drop or workflow dispatch/resume/production controls", async () => {
    renderApp("/delivery-inbox");

    await waitFor(() => expect(screen.getByRole("heading", { name: "Delivery Inbox" })).toBeDefined());
    const buttons = screen.queryAllByRole("button").map((button) => button.textContent ?? "");
    expect(buttons.some((text) => /dispatch|resume|production/i.test(text))).toBe(false);

    const newSource = [
      "src/components/Nav.tsx",
      "src/components/NavGroup.tsx",
      "src/components/PlaceholderPanel.tsx",
      "src/components/SafetyStatusBar.tsx",
      "src/pages/PlaceholderPage.tsx",
    ]
      .map((path) => sourceFile(path))
      .join("\n");
    expect(newSource).not.toMatch(/draggable|onDrag|dragStart|drop=/);
    expect(newSource).not.toMatch(/Dispatch Workflow|Resume Workflow|Production Action/);
  });
});
