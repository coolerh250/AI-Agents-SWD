// Step 62 -- Admin Console Production Deployment Readiness Gate view.
//
// READ-ONLY readiness visibility. There is intentionally NO production-deploy / ArgoCD-sync
// / GitHub-merge / image-push / restore / failover / production-approve control and NO
// production-ready toggle here. Production stays blocked and is never approved. The
// readiness decision is NOT a production approval; an operator review request is NOT an
// approval. Claude Code does not decide production readiness.
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getReadinessOverview,
  getReadinessPolicy,
  getReadinessChecklist,
  getReadinessEvidence,
  getReadinessBlockingRules,
  getReadinessPrerequisites,
  getReadinessAuthorization,
  getReadinessOperatorReviewPackage,
  getReadinessDecision,
  getReadinessPreflight,
  getReadinessSafety,
  getReadinessLimitations,
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

export function ProductionReadiness(): JSX.Element {
  return (
    <div className="production-readiness" data-testid="production-readiness">
      <h2>Production Deployment Readiness Gate (Step 62)</h2>
      <p className="note">
        Non-production readiness gate. Visibility only — NOT production deployment, NOT
        production release approval, NOT production rollout, NOT a production-ready system.
        Production is blocked and never approved: no production-deploy / ArgoCD-sync /
        GitHub-merge / image-push / restore / failover / production-approve control, no
        production-ready toggle. The readiness decision is not a production approval; an
        operator review request is not an approval; a non-production PASS is not
        production-ready. Claude Code does not decide production readiness.
      </p>
      <Section title="Overview" load={getReadinessOverview} />
      <Section title="Policy (production blocking status)" load={getReadinessPolicy} />
      <Section title="Checklist" load={getReadinessChecklist} />
      <Section title="Evidence inventory" load={getReadinessEvidence} />
      <Section title="Blocking rules" load={getReadinessBlockingRules} />
      <Section title="Production prerequisites" load={getReadinessPrerequisites} />
      <Section title="Authorization boundary" load={getReadinessAuthorization} />
      <Section title="Operator review package" load={getReadinessOperatorReviewPackage} />
      <Section title="Readiness decision" load={getReadinessDecision} />
      <Section title="Rollout preflight" load={getReadinessPreflight} />
      <Section title="Safety posture" load={getReadinessSafety} />
      <Section title="Known limitations" load={getReadinessLimitations} />
    </div>
  );
}
