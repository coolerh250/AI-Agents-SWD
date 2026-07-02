import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import { KeyValueTable } from "../components/KeyValueTable";
import { getSafetySummary, getSafety } from "../api/operations";

type Dict = Record<string, unknown>;

const loadSafety = () =>
  Promise.all([getSafetySummary(), getSafety()]).then(([summary, safety]) => ({
    summary,
    safety,
  }));

// Step 64E.4B -- Safety Center. In addition to the safety summary, explicitly
// surfaces production_executed_true_count and the live-integration disable flags
// from /operations/safety so the operator can confirm the non-production posture.
export function SafetyCenter() {
  return (
    <AsyncView load={loadSafety}>
      {({ summary, safety }) => {
        const s = safety as Dict;
        const posture: Dict[] = [
          { indicator: "production_executed_true_count", value: s.production_executed_true_count },
          {
            indicator: "workflow_production_executed_true_count",
            value: s.workflow_production_executed_true_count,
          },
          { indicator: "github_external_write_enabled", value: s.github_external_write_enabled },
          { indicator: "discord_external_send_enabled", value: s.discord_external_send_enabled },
          { indicator: "llm_external_call_enabled", value: s.llm_external_call_enabled },
          { indicator: "production_delegation_allowed", value: s.production_delegation_allowed },
        ];
        return (
          <>
            <h2>Safety Center</h2>
            <p className="note">
              Non-production staging posture. Live GitHub / Discord / LLM integrations are disabled
              or mocked; no production action.
            </p>
            <section>
              <h3>Production &amp; integration posture</h3>
              <EvidenceTable rows={posture} cols={["indicator", "value"]} />
            </section>
            <section>
              <h3>Safety summary</h3>
              <KeyValueTable data={summary as Record<string, unknown>} />
            </section>
          </>
        );
      }}
    </AsyncView>
  );
}
