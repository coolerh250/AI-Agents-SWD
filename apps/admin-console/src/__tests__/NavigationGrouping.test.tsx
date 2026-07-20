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

const EXPECTED_NAV_ROUTES = [
  "/",
  "/notifications",
  "/tasks",
  "/tasks/new",
  "/clarifications",
  "/clarification-reminders",
  "/delivery-inbox",
  "/delivery-detail",
  "/operator",
  "/incidents",
  "/agent-executions",
  "/approvals",
  "/dlq-retry",
  "/safety",
  "/audit-evidence",
  "/projects",
  "/delivery",
  "/task-graph",
  "/qa-code",
  "/design-review",
  "/workspace",
  "/mini-delivery",
  "/delivery-package",
  "/regression",
  "/cost-llm",
  "/runtime",
  "/identity",
  "/secrets",
  "/security",
  "/metrics",
  "/sandbox-github",
  "/release-governance",
  "/backup-dr",
  "/production-readiness",
  "/controlled-rollout-review",
  "/settings/roles-permissions",
  "/settings/identity-session",
  "/settings/integrations",
  "/settings/web-research-sources",
  "/settings/approval-policy",
];

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

  it("keeps Delivery Package under Platform Ops and out of Deliveries", () => {
    renderNav("/delivery-package");

    const deliveries = screen.getByTestId("nav-group-deliveries");
    expect(within(deliveries).queryByRole("link", { name: /Delivery Package/i })).toBeNull();
    expect(within(deliveries).getByRole("link", { name: /Delivery Inbox/i })).toBeDefined();
    expect(within(deliveries).getByRole("link", { name: /Delivery Detail/i })).toBeDefined();

    const platformOps = screen.getByTestId("nav-group-platform-ops");
    expect(within(platformOps).getByRole("link", { name: /Delivery Package/i })).toBeDefined();
    expect(appSource()).toContain('path="/delivery-package"');
  });

  it("preserves every existing navigation route without adding new destinations", () => {
    expect(NAV_ITEMS.map((item) => item.to)).toEqual(EXPECTED_NAV_ROUTES);
  });

  it("renders FE.1D-S1 group subtitles as visible helper text", () => {
    renderNav();

    expect(screen.getByText("Current system posture and attention")).toBeDefined();
    expect(screen.getByText("Assign and collaborate with the AI team")).toBeDefined();
    expect(screen.getByText("Review and accept delivered work")).toBeDefined();
    expect(screen.getByText("Handle operations, approvals, and recovery")).toBeDefined();
    expect(screen.getByText("Safety and audit evidence")).toBeDefined();
    expect(screen.getByText("Platform and DevOps status")).toBeDefined();
    expect(screen.getByText("Roles, integrations, and policy")).toBeDefined();
  });

  it("marks planned placeholder nav items with Soon without adding fake controls", () => {
    renderNav();

    const soonItems = [
      screen.getByRole("link", { name: /Notifications/i }),
      screen.getByRole("link", { name: /Clarifications/i }),
      screen.getByRole("link", { name: /Reminder \/ Expiry/i }),
      screen.getByRole("link", { name: /Delivery Inbox/i }),
      screen.getByRole("link", { name: /Delivery Detail/i }),
      screen.getByRole("link", { name: /Approvals/i }),
      screen.getByRole("link", { name: /DLQ \/ Retry/i }),
      screen.getByRole("link", { name: /Roles & Permissions/i }),
      screen.getByRole("link", { name: /Identity \/ Session/i }),
      screen.getByRole("link", { name: /Integrations/i }),
      screen.getByRole("link", { name: /Web Research Sources/i }),
      screen.getByRole("link", { name: /Approval Policy/i }),
    ];

    for (const item of soonItems) {
      expect(within(item).getByText("Soon")).toBeDefined();
    }
    expect(screen.queryByRole("button", { name: /^Soon$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^Soon$/i })).toBeNull();
  });

  it("renders read-only and evidence badges where navigation points to evidence or diagnostic surfaces", () => {
    renderNav("/delivery-package");

    const platformOps = screen.getByTestId("nav-group-platform-ops");
    expect(
      within(platformOps).getByRole("link", { name: /Delivery Package/i }).textContent,
    ).toMatch(/Evidence/);
    expect(within(platformOps).getByText("Delivery evidence / package record")).toBeDefined();
    expect(within(platformOps).getByRole("link", { name: /Task Graph/i }).textContent).toMatch(
      /Evidence/,
    );
    expect(within(platformOps).getByRole("link", { name: /Runtime Baseline/i }).textContent).toMatch(
      /Read-only/,
    );
    expect(within(platformOps).getByRole("link", { name: /Security/i }).textContent).toMatch(
      /Read-only/,
    );
  });

  it("keeps Platform Ops compact, collapsed by default, and shorter without changing routes", () => {
    renderNav("/delivery-package");

    const platformOpsConfig = NAV_GROUPS.find((group) => group.id === "platform-ops");
    expect(platformOpsConfig?.defaultExpanded).toBe(false);
    expect(platformOpsConfig?.compact).toBe(true);
    expect(platformOpsConfig?.items.find((item) => item.to === "/delivery")?.label).toBe(
      "Work Items",
    );
    expect(platformOpsConfig?.items.find((item) => item.to === "/task-graph")?.label).toBe(
      "Task Graph",
    );
    expect(platformOpsConfig?.items.find((item) => item.to === "/sandbox-github")?.label).toBe(
      "Sandbox GitHub",
    );
    expect(platformOpsConfig?.items.find((item) => item.to === "/delivery-package")?.label).toBe(
      "Delivery Package",
    );
  });

  it("does not introduce FE.1D Slice 2 text changes", () => {
    expect(sourceFile("src/pages/TaskList.tsx")).toContain("+ Create task");
    expect(sourceFile("src/pages/ExecutiveOverview.tsx")).toContain(
      "delivery_package_ready_for_admin_console",
    );
    expect(sourceFile("src/pages/ExecutiveOverview.tsx")).not.toContain("Ready to publish");
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

  it("renders the 66D delivery detail placeholder without workflow actions", async () => {
    renderApp("/delivery-detail");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Delivery Detail" })).toBeDefined(),
    );
    const panel = screen.getByTestId("placeholder-panel");
    expect(within(panel).getByText("Requires Step 66D.")).toBeDefined();
    expect(within(panel).getByText("No workflow action available.")).toBeDefined();
    expect(within(panel).queryByRole("button")).toBeNull();
  });

  it("renders the 66C.4 clarifications placeholder without fake controls", async () => {
    renderApp("/clarifications");

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Clarifications" })).toBeDefined(),
    );
    const panel = screen.getByTestId("placeholder-panel");
    expect(within(panel).getByText("Not yet available.")).toBeDefined();
    expect(within(panel).getByText("Requires Step 66C.4.")).toBeDefined();
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
