import { useEffect, useState } from "react";
import { getSafety } from "../api/operations";

type SafetyState =
  | { kind: "loading" }
  | { kind: "ready"; data: Record<string, unknown> }
  | { kind: "error" };

const SAFETY_FIELDS = [
  "production_executed_true_count",
  "workflow_production_executed_true_count",
  "dispatch_enabled",
  "resume_dispatch_enabled",
  "task_api_workflow_dispatch_enabled",
  "task_workroom_resume_dispatch_enabled",
  "github_external_write_enabled",
  "discord_external_send_enabled",
  "llm_external_call_enabled",
  "production_delegation_allowed",
  "approval_required",
  "requires_approval",
] as const;

function formatSafetyValue(data: Record<string, unknown>, field: string): string {
  if (!Object.prototype.hasOwnProperty.call(data, field)) return "not reported";
  const value = data[field];
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "not reported";
  return String(value);
}

export function SafetyStatusBar() {
  const [state, setState] = useState<SafetyState>({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    getSafety()
      .then((data) => {
        if (alive) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (alive) setState({ kind: "error" });
      });
    return () => {
      alive = false;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <aside className="safety-status-bar" data-testid="safety-status-bar">
        Loading safety posture...
      </aside>
    );
  }

  if (state.kind === "error") {
    return (
      <aside className="safety-status-bar" data-testid="safety-status-bar">
        Safety posture unavailable from existing endpoint.
      </aside>
    );
  }

  return (
    <aside className="safety-status-bar" data-testid="safety-status-bar">
      <span className="safety-status-label">Safety posture</span>
      {SAFETY_FIELDS.map((field) => (
        <span key={field} className="safety-status-item">
          {field}: {formatSafetyValue(state.data, field)}
        </span>
      ))}
    </aside>
  );
}
