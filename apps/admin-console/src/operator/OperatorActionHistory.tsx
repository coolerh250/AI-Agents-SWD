// Stage 52 -- operator action history (read-only view of governed actions).
import { useEffect, useState } from "react";
import { operatorActions } from "./actionClient";

interface ActionRow {
  id: string;
  action_type: string;
  target_type?: string;
  target_id?: string;
  reason?: string;
  policy_status?: string;
  status: string;
  identity_key?: string;
  requested_at?: string;
}

export function OperatorActionHistory(): JSX.Element {
  const [rows, setRows] = useState<ActionRow[]>([]);

  useEffect(() => {
    void operatorActions
      .history()
      .then((d) => setRows(((d as { actions?: ActionRow[] }).actions || []) as ActionRow[]));
  }, []);

  return (
    <div className="action-history" data-testid="action-history">
      <h3>Operator Action History</h3>
      <table>
        <thead>
          <tr>
            <th>Identity</th>
            <th>Action</th>
            <th>Target</th>
            <th>Reason</th>
            <th>Policy</th>
            <th>Status</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.identity_key}</td>
              <td>{r.action_type}</td>
              <td>{r.target_id || r.target_type}</td>
              <td>{r.reason}</td>
              <td>{r.policy_status}</td>
              <td>{r.status}</td>
              <td>{r.requested_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
