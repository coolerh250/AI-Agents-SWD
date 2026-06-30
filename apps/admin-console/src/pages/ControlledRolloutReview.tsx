// Step 63A -- Admin Console Controlled Rollout Go / No-Go Review view.
//
// READ-ONLY review visibility. There is intentionally NO production-deploy / ArgoCD-sync /
// GitHub-merge / image-push / restore / failover / production-approve control and NO
// production-ready toggle here. The go / conditional_go / no_go recommendation is NOT an
// approval and authorizes NO production action; this is the go/no-go REVIEW, not the Step 63
// rollout pilot itself. Claude Code does not decide production readiness.
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getControlledRolloutRecommendation,
  getControlledRolloutPolicy,
  getControlledRolloutCriteria,
  getControlledRolloutTarget,
  getControlledRolloutCredentials,
  getControlledRolloutGitops,
  getControlledRolloutApprovalChannel,
  getControlledRolloutRollbackDr,
  getControlledRolloutScope,
  getControlledRolloutRisks,
  getControlledRolloutDecisionPackage,
  getControlledRolloutSafety,
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

export function ControlledRolloutReview(): JSX.Element {
  return (
    <div className="controlled-rollout-review" data-testid="controlled-rollout-review">
      <h2>Controlled Rollout Go / No-Go Review (Step 63A)</h2>
      <p className="note">
        Non-production go/no-go REVIEW — NOT the Step 63 rollout pilot, NOT production
        deployment, NOT production release approval, NOT production rollout. The
        go / conditional_go / no_go recommendation is not an approval and authorizes no
        production action. Production is blocked and never approved: no production-deploy /
        ArgoCD-sync / GitHub-merge / image-push / restore / failover / production-approve
        control, no production-ready toggle. A future pilot requires explicit operator approval
        in a separate stage. Claude Code does not decide production readiness.
      </p>
      <Section title="Recommendation" load={getControlledRolloutRecommendation} />
      <Section title="Review policy" load={getControlledRolloutPolicy} />
      <Section title="Go / No-Go criteria" load={getControlledRolloutCriteria} />
      <Section title="Production target assessment" load={getControlledRolloutTarget} />
      <Section title="Credential readiness" load={getControlledRolloutCredentials} />
      <Section title="GitOps readiness" load={getControlledRolloutGitops} />
      <Section title="Approval channel readiness" load={getControlledRolloutApprovalChannel} />
      <Section title="Rollback / DR readiness" load={getControlledRolloutRollbackDr} />
      <Section title="Pilot scope" load={getControlledRolloutScope} />
      <Section title="Risk register" load={getControlledRolloutRisks} />
      <Section title="Operator decision package" load={getControlledRolloutDecisionPackage} />
      <Section title="Safety posture" load={getControlledRolloutSafety} />
    </div>
  );
}
