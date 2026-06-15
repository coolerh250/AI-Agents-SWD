import { useParams } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { KeyValueTable } from "../components/KeyValueTable";
import { getProjectDetail } from "../api/operations";

export function ProjectDetail() {
  const { projectId = "" } = useParams();
  return (
    <AsyncView load={() => getProjectDetail(projectId)}>
      {(d) => (
        <>
          <h2>Project Detail</h2>
          <h3>Rollup</h3>
          <KeyValueTable data={d.rollup as unknown as Record<string, unknown>} />
          <h3>Project</h3>
          <KeyValueTable data={d.project} />
          <h3>Latest pilot</h3>
          <KeyValueTable data={d.latest_pilot} />
          <h3>Latest delivery package</h3>
          <KeyValueTable data={d.latest_delivery_package} />
        </>
      )}
    </AsyncView>
  );
}
