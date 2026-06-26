// Step 59 -- Admin Console Sandbox GitHub Draft PR view.
//
// READ-ONLY visibility over the sandbox draft-PR policy / allowlist / requests / safety.
// There is intentionally NO create / merge / ready-for-review / workflow-dispatch /
// production-deploy control, NO arbitrary repo input, and NO token input here. Sandbox
// draft PR requests are made through the governed orchestrator endpoint (auth + CSRF +
// audit), not from this dashboard. Draft PR created is NOT merge, review, or production
// approved.
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import {
  getSandboxGithubPolicy,
  getSandboxGithubAllowlist,
  getSandboxGithubRequests,
  getSandboxGithubSafety,
  getSandboxGithubReadiness,
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

export function SandboxGithub(): JSX.Element {
  return (
    <div className="sandbox-github" data-testid="sandbox-github">
      <h2>Sandbox GitHub Draft PR (Step 59)</h2>
      <p className="note">
        Sandbox-only draft pull request flow. Visibility only — NOT production GitHub
        automation, NOT merge automation, NOT a customer-repo flow. Default mode is dry_run;
        live_sandbox is blocked unless explicitly enabled with a credential. This view has NO
        create / merge / ready-for-review / workflow-dispatch / production-deploy control, NO
        arbitrary repo input, and NO token input. Draft PR created is not merge, review, or
        production approved. Claude Code does not decide production readiness.
      </p>
      <Section title="Policy" load={getSandboxGithubPolicy} />
      <Section title="Repository allowlist" load={getSandboxGithubAllowlist} />
      <Section title="Readiness (live mode gate)" load={getSandboxGithubReadiness} />
      <Section title="Draft PR requests" load={getSandboxGithubRequests} />
      <Section title="Safety posture" load={getSandboxGithubSafety} />
    </div>
  );
}
