import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { CalmSafetyPosture, getCalmSafetyPosture } from "../components/CalmSafetyPosture";

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

describe("CalmSafetyPosture", () => {
  it("presents the sanitized real-schema fixture as safe while preserving raw evidence", () => {
    render(<CalmSafetyPosture data={SAFE_SAFETY} />);

    expect(screen.getByText("Safe")).toBeDefined();
    expect(screen.getByText("Safe - no automated or production actions will run.")).toBeDefined();
    expect(screen.getByText("No production actions have run")).toBeDefined();
    expect(screen.getByText("Automated workflow dispatch: Off")).toBeDefined();
    expect(screen.getByText("External integrations: Off")).toBeDefined();
    expect(
      screen.getByText(
        "Approvals are tracked per task. Review task details for approval requirements.",
      ),
    ).toBeDefined();

    const summary = screen.getByText("Safe - no automated or production actions will run.").closest(
      ".calm-safety-summary",
    );
    expect(summary?.textContent).not.toMatch(/production_executed_true_count|dispatch_enabled/);

    expect(screen.getAllByText(/production_executed_true_count/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/workflow_dispatch/).length).toBeGreaterThan(0);
    expect(screen.getByText(/github_external_write_enabled/)).toBeDefined();
  });

  it("does not require task-scoped dispatch or approval fields for a safe global posture", () => {
    const posture = getCalmSafetyPosture(SAFE_SAFETY);

    expect(posture.tone).toBe("safe");
    expect(posture.facts).toContain(
      "Approvals are tracked per task. Review task details for approval requirements.",
    );
  });

  it("falls back honestly when truly required global safety fields are missing", () => {
    render(<CalmSafetyPosture data={{ production_executed_true_count: 0 }} />);

    expect(screen.getByText("Unavailable")).toBeDefined();
    expect(screen.getByText("Safety status unavailable - check system evidence.")).toBeDefined();
    expect(screen.getByText("Automated workflow dispatch: not reported")).toBeDefined();
    expect(screen.getAllByText("not reported").length).toBeGreaterThan(0);
  });

  it.each([
    "task_api_workflow_dispatch_enabled",
    "task_workroom_resume_dispatch_enabled",
  ])("shows attention when %s is enabled", (field) => {
    const posture = getCalmSafetyPosture({ ...SAFE_SAFETY, [field]: true });

    expect(posture.tone).toBe("attention");
    expect(posture.label).not.toBe("Safe");
  });

  it("shows attention when a production action count is positive", () => {
    const posture = getCalmSafetyPosture({ ...SAFE_SAFETY, production_executed_true_count: 1 });

    expect(posture.tone).toBe("attention");
    expect(posture.label).not.toBe("Safe");
  });

  it.each([
    "github_external_write_enabled",
    "discord_external_send_enabled",
    "llm_external_call_enabled",
  ])("shows attention when %s is enabled", (field) => {
    const posture = getCalmSafetyPosture({ ...SAFE_SAFETY, [field]: true });

    expect(posture.tone).toBe("attention");
    expect(posture.label).not.toBe("Safe");
  });

  it("requires the endpoint result and production delegation evidence before showing safe", () => {
    const { result: _result, ...withoutResult } = SAFE_SAFETY;
    const { production_delegation_allowed: _delegation, ...withoutDelegation } = SAFE_SAFETY;

    expect(getCalmSafetyPosture(withoutResult).tone).toBe("unavailable");
    expect(getCalmSafetyPosture(withoutDelegation).tone).toBe("unavailable");
  });

  it("labels retired endpoint fields as not applicable", () => {
    render(<CalmSafetyPosture data={SAFE_SAFETY} />);

    expect(screen.getAllByText("Not applicable at this endpoint")).toHaveLength(4);
    expect(screen.getByText("dispatch_enabled", { selector: ".calm-safety-field" })).toBeDefined();
    expect(
      screen.getByText("resume_dispatch_enabled", { selector: ".calm-safety-field" }),
    ).toBeDefined();
    expect(screen.getByText("approval_required", { selector: ".calm-safety-field" })).toBeDefined();
    expect(screen.getByText("requires_approval", { selector: ".calm-safety-field" })).toBeDefined();
  });

  it("renders compact mode without hiding technical details", () => {
    render(<CalmSafetyPosture data={SAFE_SAFETY} compact />);

    expect(screen.queryByLabelText("Safety facts")).toBeNull();
    expect(screen.getByText("Evidence / details")).toBeDefined();
    const details = screen.getByText("Evidence / details").closest("details");
    expect(details).toBeDefined();
    expect(
      within(details as HTMLElement).getAllByText(/task_workroom_resume_dispatch_enabled/).length,
    ).toBeGreaterThan(0);
  });
});
