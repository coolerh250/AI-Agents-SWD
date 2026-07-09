import { NavLink } from "react-router-dom";

export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "Executive Overview" },
  // Step 66B.2 -- AI Agents Team Work operator task assignment (test-only auth).
  { to: "/tasks", label: "Tasks" },
  { to: "/projects", label: "Projects" },
  { to: "/delivery", label: "Projects / Work Items" },
  { to: "/agent-executions", label: "Agent Executions" },
  { to: "/task-graph", label: "Workflows / Task Graph" },
  { to: "/qa-code", label: "QA / Code" },
  { to: "/audit-evidence", label: "Audit / Evidence" },
  { to: "/design-review", label: "Design Review" },
  { to: "/workspace", label: "Workspace Execution" },
  { to: "/mini-delivery", label: "Mini Delivery Pilot" },
  { to: "/delivery-package", label: "Delivery Package" },
  { to: "/safety", label: "Safety Center" },
  { to: "/regression", label: "Regression" },
  { to: "/cost-llm", label: "Cost / LLM" },
  { to: "/incidents", label: "Incidents" },
  { to: "/operator", label: "Operator Console" },
  { to: "/runtime", label: "Runtime Baseline" },
  { to: "/identity", label: "Identity Posture" },
  { to: "/secrets", label: "Secret Posture" },
  { to: "/security", label: "Security / Supply Chain" },
  { to: "/metrics", label: "Operational Metrics" },
  { to: "/sandbox-github", label: "Sandbox GitHub Draft PR" },
  { to: "/release-governance", label: "Release Governance" },
  { to: "/backup-dr", label: "Backup / Restore / DR" },
  { to: "/production-readiness", label: "Production Readiness Gate" },
  { to: "/controlled-rollout-review", label: "Controlled Rollout Review" },
  // Developer diagnostic only -- NOT a staging acceptance path (Step 64E.4A policy).
  { to: "/demo-evidence", label: "Diagnostics (Demo Evidence)" },
];

export function Nav() {
  return (
    <nav>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
