// Step 60 -- Admin Console Release Governance view.
//
// READ-ONLY governance visibility. There is intentionally NO production-deploy / ArgoCD
// sync / PR merge / GitHub release / image-push / production-approve control and NO
// production-ready toggle here. Production stays blocked. A release candidate marked
// accepted_nonproduction is NOT a production approval; a deployment intent never executes
// a deployment. Claude Code does not decide production readiness.
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getReleaseOverview,
  getReleasePolicy,
  getReleaseCandidates,
  getReleaseDeploymentIntents,
  getReleaseReadinessSummary,
  getReleaseSafety,
  getReleaseLimitations,
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

export function ReleaseGovernance(): JSX.Element {
  return (
    <div className="release-governance" data-testid="release-governance">
      <h2>Release Governance (Step 60)</h2>
      <p className="note">
        Non-production release & deployment governance. Visibility only — NOT production
        deployment, NOT production release approval, NOT auto-promotion, NOT production GitOps.
        Production is blocked: no production-deploy / ArgoCD production sync / PR merge / GitHub
        release / image-push control, no production-ready toggle. A release candidate marked
        accepted_nonproduction is not a production approval; a deployment intent never executes a
        deployment; a human-review request is not a human approval. Claude Code does not decide
        production readiness.
      </p>
      <Section title="Overview" load={getReleaseOverview} />
      <Section title="Policy (production blocking status)" load={getReleasePolicy} />
      <Section title="Release candidates" load={getReleaseCandidates} />
      <Section title="Deployment intents" load={getReleaseDeploymentIntents} />
      <Section title="Readiness summary" load={getReleaseReadinessSummary} />
      <Section title="Safety posture" load={getReleaseSafety} />
      <Section title="Known limitations" load={getReleaseLimitations} />
    </div>
  );
}
