import { useState } from "react";
import { AsyncView } from "../components/AsyncView";
import { EvidenceTable } from "../components/EvidenceTable";
import { getTeam, getTeamMessages, getTeamRoutingDecisions } from "../api/operations";

type Dict = Record<string, unknown>;

// Step AT-M2-TEAM-CORE -- minimal read-only Team Room. Shows the three facts AT-M2 has to be
// judged on: who is on the team and what they declare, who addressed whom, and why the runtime
// chose each successor. GET-only; no assignment control, no dispatch, no production action.
// The full Autonomous Team UX is AT-M5, deliberately not attempted here.
export function TeamRoom() {
  const [projectId, setProjectId] = useState("");
  const [submitted, setSubmitted] = useState("");

  return (
    <>
      <h2>Team Room</h2>
      <p className="note">
        Read-only view of a project's runtime team, its addressed conversation, and its routing
        decisions. production_executed=false; no production action.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(projectId.trim());
        }}
      >
        <label htmlFor="team-project-id">Project id</label>{" "}
        <input
          id="team-project-id"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          placeholder="project uuid"
        />{" "}
        <button type="submit">View team</button>
      </form>
      {submitted ? <TeamPanels projectId={submitted} /> : <p className="note">Enter a project id.</p>}
    </>
  );
}

function TeamPanels({ projectId }: { projectId: string }) {
  return (
    <>
      <h3>Members and declared capabilities</h3>
      <AsyncView load={() => getTeam(projectId)}>
        {(d) => (
          <EvidenceTable
            rows={((d as Dict).members as Dict[]) || []}
            cols={["agent_key", "functional_role", "membership_state", "capabilities", "principal_type"]}
            empty="No team has been formed for this project"
          />
        )}
      </AsyncView>

      <h3>Addressed messages</h3>
      <AsyncView load={() => getTeamMessages(projectId)}>
        {(d) => (
          <EvidenceTable
            rows={((d as Dict).messages as Dict[]) || []}
            cols={["message_type", "recipient_role", "summary", "parent_message_id", "created_at"]}
            empty="No team messages yet"
          />
        )}
      </AsyncView>

      <h3>Routing decisions</h3>
      <p className="note">
        Why the runtime chose each successor. An outcome of no_eligible_agent is the honest answer
        when the team has nobody who declares the capability — never a fallback to a fixed agent.
      </p>
      <AsyncView load={() => getTeamRoutingDecisions(projectId)}>
        {(d) => (
          <EvidenceTable
            rows={((d as Dict).routing_decisions as Dict[]) || []}
            cols={["requested_capability", "outcome", "selected_role", "reason", "created_at"]}
            empty="No routing decisions yet"
          />
        )}
      </AsyncView>
    </>
  );
}
