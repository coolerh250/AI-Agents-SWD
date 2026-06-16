// Stage 52 -- allowlisted verification rerun page. No custom command / args.
import { useState } from "react";
import { operatorActions } from "./actionClient";
import { ConfirmDialog } from "./ConfirmDialog";

// Allowlist is fixed client-side too (the backend is authoritative). There is
// deliberately NO free-text command or argument input.
const ALLOWLISTED = [
  "delivery_package_acceptance_gate",
  "admin_console_v0",
  "backup_dr_gap_closure",
  "audit_integrity",
  "full_regression",
];

export function VerificationRerunPage(): JSX.Element {
  const [scriptKey, setScriptKey] = useState(ALLOWLISTED[0]);
  const [confirming, setConfirming] = useState(false);
  const [status, setStatus] = useState("");

  async function start(reason: string): Promise<void> {
    setConfirming(false);
    await operatorActions.refreshCsrf();
    const highRisk = scriptKey === "full_regression";
    const resp = (await operatorActions.rerunVerification(scriptKey, reason, highRisk)) as {
      action_id?: string;
      confirmation_nonce?: string;
      status?: string;
    };
    if (resp.confirmation_nonce && resp.action_id) {
      setStatus("running…");
      const run = await operatorActions.runVerification(resp.action_id, resp.confirmation_nonce);
      setStatus(JSON.stringify(run));
    } else {
      setStatus(JSON.stringify(resp));
    }
  }

  return (
    <div className="verification-rerun" data-testid="verification-rerun">
      <h3>Rerun Verification</h3>
      <label>
        Verification (allowlisted only)
        <select value={scriptKey} onChange={(e) => setScriptKey(e.target.value)}>
          {ALLOWLISTED.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </label>
      <button data-testid="rerun-start" onClick={() => setConfirming(true)}>
        Run
      </button>
      {confirming ? (
        <ConfirmDialog
          title={`Confirm rerun: ${scriptKey}`}
          onConfirm={(reason) => void start(reason)}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
      {status ? <pre className="rerun-result">{status}</pre> : null}
    </div>
  );
}
