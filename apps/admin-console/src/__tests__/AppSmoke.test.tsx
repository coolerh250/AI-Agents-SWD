import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ExecutiveOverview } from "../pages/ExecutiveOverview";
import { Projects } from "../pages/Projects";
import { SafetyCenter } from "../pages/SafetyCenter";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, status, json: async () => body }),
  );
}

describe("App smoke", () => {
  it("renders attention-first Overview with mock data", async () => {
    mockFetch({
      active_projects_count: 1,
      delivery_packages_count: 1,
      ready_for_review_packages_count: 1,
      latest_mini_delivery_pilot_status: "completed",
      latest_delivery_package_status: "ready_for_review",
      latest_acceptance_gate_decision: "ready_for_operator_review",
      latest_human_acceptance_status: "pending",
      safety_result: "safe",
      production_executed_true_count: 0,
      delivery_package_ready_for_admin_console: true,
      latest_full_regression_status: "passed_with_documented_gaps",
      backup_readiness_gaps: ["encryption_no_key"],
      incidents_summary: {},
      llm_summary: {},
      admin_console: {},
    });
    render(
      <MemoryRouter>
        <ExecutiveOverview />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Overview")).toBeDefined());
    expect(screen.getByText("Needs your attention")).toBeDefined();
  });

  it("renders empty Projects state", async () => {
    mockFetch({ count: 0, projects: [] });
    render(
      <MemoryRouter>
        <Projects />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("No projects yet")).toBeDefined());
  });

  it("renders error state on API failure", async () => {
    mockFetch({}, false, 503);
    render(
      <MemoryRouter>
        <SafetyCenter />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Unable to load data/)).toBeDefined());
  });
});
