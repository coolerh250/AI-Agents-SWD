// Stage 52 -- delivery package operator review panel (role-aware actions).
import { useEffect, useState } from "react";
import { operatorActions, SessionInfo } from "./actionClient";
import { ConfirmDialog } from "./ConfirmDialog";

type ActionKind = "accept" | "reject" | "request_changes" | "note";

function canDo(role: string | undefined, kind: ActionKind): boolean {
  if (kind === "note" || kind === "request_changes")
    return role === "reviewer" || role === "operator" || role === "platform_admin";
  return role === "operator" || role === "platform_admin"; // accept / reject
}

export function OperatorReviewPanel({ packageId }: { packageId: string }): JSX.Element {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [pending, setPending] = useState<ActionKind | null>(null);
  const [result, setResult] = useState<string>("");

  useEffect(() => {
    void operatorActions.session().then(setSession);
  }, []);

  const role = session?.role;

  async function perform(kind: ActionKind, reason: string): Promise<void> {
    setPending(null);
    await operatorActions.refreshCsrf();
    let resp: unknown;
    if (kind === "note") resp = await operatorActions.addNote(packageId, reason);
    else if (kind === "request_changes") resp = await operatorActions.requestChanges(packageId, reason);
    else if (kind === "accept") resp = await operatorActions.accept(packageId, reason);
    else resp = await operatorActions.reject(packageId, reason);

    // accept / reject / request_changes require a second confirmation nonce.
    const r = resp as { action_id?: string; confirmation_nonce?: string; status?: string };
    if (r.confirmation_nonce && r.action_id) {
      const exec = await operatorActions.confirmAndExecute(r.action_id, r.confirmation_nonce);
      setResult(JSON.stringify(exec));
    } else {
      setResult(JSON.stringify(resp));
    }
  }

  if (!session?.authenticated)
    return <div className="review-panel">Sign in as an operator to act on this package.</div>;

  const buttons: { kind: ActionKind; label: string }[] = [
    { kind: "note", label: "Add Note" },
    { kind: "request_changes", label: "Request Changes" },
    { kind: "accept", label: "Accept" },
    { kind: "reject", label: "Reject" },
  ];

  return (
    <div className="review-panel" data-testid="operator-review-panel">
      <div className="review-actions">
        {buttons.map((b) => (
          <button
            key={b.kind}
            disabled={!canDo(role, b.kind)}
            data-testid={`action-${b.kind}`}
            onClick={() => setPending(b.kind)}
          >
            {b.label}
          </button>
        ))}
      </div>
      {pending ? (
        <ConfirmDialog
          title={`Confirm: ${pending}`}
          onConfirm={(reason) => void perform(pending, reason)}
          onCancel={() => setPending(null)}
        />
      ) : null}
      {result ? <pre className="action-result">{result}</pre> : null}
    </div>
  );
}
