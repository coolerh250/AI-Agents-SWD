// Step 61 -- Admin Console Backup / Restore / DR Operations view.
//
// READ-ONLY governance visibility. There is intentionally NO execute-cleanup / execute-
// restore / failover / teardown-kind / ArgoCD-sync / cloud-upload control and NO
// production-ready toggle here. Production restore and production failover stay blocked. A
// cleanup review never deletes anything; a restore plan never executes a restore; DR
// readiness is NOT production DR ready. Claude Code does not decide production readiness.
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getDrOverview,
  getDrPolicy,
  getDrInventory,
  getDrCleanupReview,
  getDrRestorePlans,
  getDrRestoreValidations,
  getDrEvidence,
  getDrReadiness,
  getDrSafety,
  getDrLimitations,
} from "../api/operations";

type Dict = Record<string, unknown>;

function Section({ title, load }: { title: string; load: () => Promise<Dict> }): JSX.Element {
  return (
    <section>
      <h3>{title}</h3>
      <AsyncView load={load}>{(d) => <KeyValueTable data={d as Dict} />}</AsyncView>
    </section>
  );
}

export function BackupDr(): JSX.Element {
  return (
    <div className="backup-dr" data-testid="backup-dr">
      <h2>Backup / Restore / DR Operations (Step 61)</h2>
      <p className="note">
        Non-production backup / restore / disaster-recovery governance. Visibility only — NOT
        production restore, NOT production failover, NOT production data mutation, NOT cleanup
        execution, NOT restore execution. Production is blocked: no execute-cleanup / execute-
        restore / failover / teardown-kind / ArgoCD-sync / cloud-upload control, no production-
        ready toggle. A cleanup review never deletes anything; a restore plan never executes a
        restore; DR readiness is a governance judgement, not production DR ready. Claude Code
        does not decide production readiness.
      </p>
      <Section title="Overview" load={getDrOverview} />
      <Section title="Policy (production blocking status)" load={getDrPolicy} />
      <Section title="Backup target inventory & artifact classification" load={getDrInventory} />
      <Section title="Cleanup review (review only — no execution)" load={getDrCleanupReview} />
      <Section title="Restore plans (plan only — no execution)" load={getDrRestorePlans} />
      <Section title="Restore validations" load={getDrRestoreValidations} />
      <Section title="Recovery evidence" load={getDrEvidence} />
      <Section title="DR readiness" load={getDrReadiness} />
      <Section title="Safety posture" load={getDrSafety} />
      <Section title="Known limitations" load={getDrLimitations} />
    </div>
  );
}
