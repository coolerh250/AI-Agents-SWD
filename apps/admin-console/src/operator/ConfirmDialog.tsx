// Stage 52 -- mandatory-reason confirmation dialog for operator actions.
import { useState } from "react";

interface Props {
  title: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function ConfirmDialog({ title, onConfirm, onCancel }: Props): JSX.Element {
  const [reason, setReason] = useState("");
  return (
    <div className="confirm-dialog" role="dialog" data-testid="confirm-dialog">
      <h4>{title}</h4>
      <p className="action-disclaimer">
        This action does not deploy, create a PR, or execute production changes.
      </p>
      <label>
        Reason (required)
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <div>
        <button
          disabled={!reason.trim()}
          data-testid="confirm-submit"
          onClick={() => onConfirm(reason.trim())}
        >
          Confirm
        </button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
