import { useEffect, useState } from "react";
import { getSafety } from "../api/operations";
import { CalmSafetyPosture } from "./CalmSafetyPosture";

type SafetyState =
  | { kind: "loading" }
  | { kind: "ready"; data: Record<string, unknown> }
  | { kind: "error" };

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
        Checking safety posture...
      </aside>
    );
  }

  if (state.kind === "error") {
    return (
      <aside className="safety-status-bar" data-testid="safety-status-bar">
        <div className="calm-safety calm-safety-unavailable">
          <div className="calm-safety-summary">
            <span className="badge safety-posture-badge safety-posture-unavailable">
              Unavailable
            </span>
            <span className="calm-safety-title">
              Safety status unavailable - check system evidence.
            </span>
          </div>
          <details className="calm-safety-details">
            <summary>Evidence / details</summary>
            <p className="note">The existing /operations/safety endpoint could not be loaded.</p>
          </details>
        </div>
      </aside>
    );
  }

  return (
    <aside className="safety-status-bar" data-testid="safety-status-bar">
      <CalmSafetyPosture data={state.data} compact />
    </aside>
  );
}
