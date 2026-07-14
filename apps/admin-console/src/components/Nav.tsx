import { NavGroup } from "./NavGroup";

export type NavItem = {
  to: string;
  label: string;
  end?: boolean;
};

export type NavGroupConfig = {
  id: string;
  label: string;
  items: NavItem[];
  collapsible?: boolean;
  defaultExpanded?: boolean;
};

export const NAV_GROUPS: NavGroupConfig[] = [
  {
    id: "overview",
    label: "Overview",
    items: [
      { to: "/", label: "Dashboard", end: true },
      { to: "/notifications", label: "Notifications" },
    ],
  },
  {
    id: "team-work",
    label: "Team Work",
    items: [
      { to: "/tasks", label: "Tasks", end: true },
      { to: "/tasks/new", label: "Create Task", end: true },
      { to: "/clarifications", label: "Clarifications", end: true },
      { to: "/clarification-reminders", label: "Reminder / Expiry", end: true },
    ],
  },
  {
    id: "deliveries",
    label: "Deliveries",
    items: [
      { to: "/delivery-inbox", label: "Delivery Inbox", end: true },
      { to: "/delivery-detail", label: "Delivery Detail", end: true },
      { to: "/delivery-package", label: "Delivery Package" },
    ],
  },
  {
    id: "operator-center",
    label: "Operator Center",
    items: [
      { to: "/operator", label: "Operator Console" },
      { to: "/incidents", label: "Incidents" },
      { to: "/agent-executions", label: "Agent Executions" },
      { to: "/approvals", label: "Approvals" },
      { to: "/dlq-retry", label: "DLQ / Retry" },
    ],
  },
  {
    id: "governance",
    label: "Governance",
    items: [
      { to: "/safety", label: "Safety Center" },
      { to: "/audit-evidence", label: "Audit Evidence" },
    ],
  },
  {
    id: "platform-ops",
    label: "Platform Ops",
    collapsible: true,
    defaultExpanded: false,
    items: [
      { to: "/projects", label: "Projects" },
      { to: "/delivery", label: "Projects / Work Items" },
      { to: "/task-graph", label: "Workflows / Task Graph" },
      { to: "/qa-code", label: "QA / Code" },
      { to: "/design-review", label: "Design Review" },
      { to: "/workspace", label: "Workspace Execution" },
      { to: "/mini-delivery", label: "Mini Delivery Pilot" },
      { to: "/regression", label: "Regression" },
      { to: "/cost-llm", label: "Cost / LLM" },
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
    ],
  },
  {
    id: "settings",
    label: "Settings",
    items: [
      { to: "/settings/roles-permissions", label: "Roles & Permissions" },
      { to: "/settings/identity-session", label: "Identity / Session" },
      { to: "/settings/integrations", label: "Integrations" },
      { to: "/settings/web-research-sources", label: "Web Research Sources" },
      { to: "/settings/approval-policy", label: "Approval Policy" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

export function Nav() {
  return (
    <nav className="side-nav" aria-label="Admin Console">
      {NAV_GROUPS.map((group) => (
        <NavGroup key={group.id} group={group} />
      ))}
    </nav>
  );
}
