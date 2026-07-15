import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { CalmSafetyPosture, getCalmSafetyPosture } from "../components/CalmSafetyPosture";

const SAFE_SAFETY = {
  production_executed_true_count: 0,
  workflow_production_executed_true_count: 0,
  dispatch_enabled: false,
  resume_dispatch_enabled: false,
  task_api_workflow_dispatch_enabled: false,
  task_workroom_resume_dispatch_enabled: false,
  github_external_write_enabled: false,
  discord_external_send_enabled: false,
  llm_external_call_enabled: false,
  production_delegation_allowed: false,
  approval_required: false,
  requires_approval: false,
  result: "safe",
};

describe("CalmSafetyPosture", () => {
  it("presents a safe posture in product language while preserving raw evidence", () => {
    render(<CalmSafetyPosture data={SAFE_SAFETY} />);

    expect(screen.getByText("Safe")).toBeDefined();
    expect(screen.getByText("Safe - no automated or production actions will run.")).toBeDefined();
    expect(screen.getByText("No production actions have run")).toBeDefined();
    expect(screen.getByText("Automated workflow dispatch: Off")).toBeDefined();
    expect(screen.getByText("External integrations: Off")).toBeDefined();

    const summary = screen.getByText("Safe - no automated or production actions will run.").closest(
      ".calm-safety-summary",
    );
    expect(summary?.textContent).not.toMatch(/production_executed_true_count|dispatch_enabled/);

    expect(screen.getAllByText(/production_executed_true_count/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/workflow_dispatch/).length).toBeGreaterThan(0);
    expect(screen.getByText(/github_external_write_enabled/)).toBeDefined();
  });

  it("does not claim safe when approval is required", () => {
    const posture = getCalmSafetyPosture({ ...SAFE_SAFETY, approval_required: true });

    expect(posture.tone).toBe("attention");
    expect(posture.title).toBe("Attention needed - items are awaiting approval.");
    expect(posture.facts).toContain("Human approval is required before anything runs");
  });

  it("falls back honestly when required safety fields are missing", () => {
    render(<CalmSafetyPosture data={{ production_executed_true_count: 0 }} />);

    expect(screen.getByText("Unavailable")).toBeDefined();
    expect(screen.getByText("Safety status unavailable - check system evidence.")).toBeDefined();
    expect(screen.getByText("Automated workflow dispatch: not reported")).toBeDefined();
    expect(screen.getAllByText("not reported").length).toBeGreaterThan(0);
  });

  it("renders compact mode without hiding technical details", () => {
    render(<CalmSafetyPosture data={SAFE_SAFETY} compact />);

    expect(screen.queryByLabelText("Safety facts")).toBeNull();
    expect(screen.getByText("Evidence / details")).toBeDefined();
    const details = screen.getByText("Evidence / details").closest("details");
    expect(details).toBeDefined();
    expect(
      within(details as HTMLElement).getAllByText(/resume_dispatch_enabled/).length,
    ).toBeGreaterThan(0);
  });
});
