import { AsyncView } from "../components/AsyncView";
import { CalmSafetyPosture } from "../components/CalmSafetyPosture";
import { KeyValueTable } from "../components/KeyValueTable";
import { getSafetySummary, getSafety } from "../api/operations";

type Dict = Record<string, unknown>;

const loadSafety = () =>
  Promise.all([getSafetySummary(), getSafety()]).then(([summary, safety]) => ({
    summary,
    safety,
  }));

export function SafetyCenter() {
  return (
    <AsyncView load={loadSafety}>
      {({ summary, safety }) => {
        const s = safety as Dict;
        return (
          <>
            <h2>Safety Center</h2>
            <p className="note">
              Existing /operations/safety evidence, translated into product language first.
            </p>
            <section className="safety-panel">
              <h3>Safety posture</h3>
              <CalmSafetyPosture data={s} />
            </section>
            <section>
              <h3>Admin Console safety summary</h3>
              <KeyValueTable data={summary as Record<string, unknown>} />
            </section>
          </>
        );
      }}
    </AsyncView>
  );
}
