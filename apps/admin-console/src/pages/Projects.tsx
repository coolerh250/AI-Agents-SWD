import { Link } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { getProjects } from "../api/operations";

export function Projects() {
  return (
    <AsyncView load={getProjects}>
      {(d) =>
        d.projects.length === 0 ? (
          <>
            <h2>Projects</h2>
            <EmptyState message="No projects yet" />
          </>
        ) : (
          <>
            <h2>Projects</h2>
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Autonomy</th>
                  <th>Pilot</th>
                  <th>Package</th>
                  <th>Readiness</th>
                  <th>Human acceptance</th>
                </tr>
              </thead>
              <tbody>
                {d.projects.map((p) => (
                  <tr key={p.project_id}>
                    <td>
                      <Link to={`/projects/${p.project_id}`}>{p.title || p.project_id}</Link>
                    </td>
                    <td>
                      <StatusBadge value={p.status} />
                    </td>
                    <td>
                      <StatusBadge value={p.risk_level} />
                    </td>
                    <td>
                      <StatusBadge value={p.autonomy_level} />
                    </td>
                    <td>
                      <StatusBadge value={p.latest_pilot_status} />
                    </td>
                    <td>
                      <StatusBadge value={p.latest_delivery_package_status} />
                    </td>
                    <td>
                      <StatusBadge value={p.readiness_status} />
                    </td>
                    <td>
                      <StatusBadge value={p.human_acceptance_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )
      }
    </AsyncView>
  );
}
