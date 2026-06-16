// Stage 52 -- Admin Console v1 Operator Console page.
import { useState } from "react";
import { SessionBanner } from "../operator/SessionBanner";
import { OperatorReviewPanel } from "../operator/OperatorReviewPanel";
import { VerificationRerunPage } from "../operator/VerificationRerunPage";
import { OperatorActionHistory } from "../operator/OperatorActionHistory";
import { DisabledFutureActions } from "../operator/DisabledFutureActions";

export function OperatorConsole(): JSX.Element {
  const [packageId, setPackageId] = useState("");
  return (
    <div className="operator-console" data-testid="operator-console">
      <h2>Operator Console (v1, controlled actions)</h2>
      <SessionBanner />
      <section>
        <h3>Delivery Package Review</h3>
        <label>
          Package ID
          <input value={packageId} onChange={(e) => setPackageId(e.target.value)} />
        </label>
        {packageId ? <OperatorReviewPanel packageId={packageId} /> : null}
      </section>
      <VerificationRerunPage />
      <OperatorActionHistory />
      <DisabledFutureActions />
    </div>
  );
}
