import { NavGroup } from "./NavGroup";

export type NavItem = {
  to: string;
  label: string;
  subtitle?: string;
  badge?: "Soon" | "Read-only" | "Evidence";
  end?: boolean;
};

export type NavGroupConfig = {
  id: string;
  label: string;
  subtitle?: string;
  items: NavItem[];
  collapsible?: boolean;
  defaultExpanded?: boolean;
  compact?: boolean;
};

export const NAV_GROUPS: NavGroupConfig[] = [
  {
    id: "overview",
    label: "Overview",
    subtitle: "Current system posture and attention",
    items: [
      { to: "/", label: "Dashboard", end: true },
      { to: "/notifications", label: "Notifications", badge: "Soon" },
    ],
  },
  {
    id: "team-work",
    label: "Team Work",
    subtitle: "Assign and collaborate with the AI team",
    items: [
      { to: "/tasks", label: "Tasks", end: true },
      { to: "/tasks/new", label: "Create Task", end: true },
      { to: "/clarifications", label: "Clarifications", badge: "Soon", end: true },
      { to: "/clarification-reminders", label: "Reminder / Expiry", badge: "Soon", end: true },
    ],
  },
  {
    id: "deliveries",
    label: "Deliveries",
    subtitle: "Review and accept delivered work",
    items: [
      { to: "/delivery-inbox", label: "Delivery Inbox", badge: "Soon", end: true },
      { to: "/delivery-detail", label: "Delivery Detail", badge: "Soon", end: true },
    ],
  },
  {
    id: "operator-center",
    label: "Operator Center",
    subtitle: "Handle operations, approvals, and recovery",
    items: [
      { to: "/operator", label: "Operator Console" },
      { to: "/incidents", label: "Incidents" },
      { to: "/agent-executions", label: "Agent Executions", badge: "Evidence" },
      { to: "/approvals", label: "Approvals", badge: "Soon" },
      { to: "/dlq-retry", label: "DLQ / Retry", badge: "Soon" },
    ],
  },
  {
    id: "governance",
    label: "Governance",
    subtitle: "Safety and audit evidence",
    items: [
      { to: "/safety", label: "Safety Center", badge: "Read-only" },
      { to: "/audit-evidence", label: "Audit Evidence", badge: "Evidence" },
    ],
  },
  {
    id: "platform-ops",
    label: "Platform Ops",
    subtitle: "Platform and DevOps status",
    collapsible: true,
    defaultExpanded: false,
    compact: true,
    items: [
      { to: "/projects", label: "Projects" },
      {
        to: "/delivery",
        label: "Work Items",
        subtitle: "Multi-project delivery",
        badge: "Read-only",
      },
      { to: "/task-graph", label: "Task Graph", badge: "Evidence" },
      { to: "/qa-code", label: "QA / Code", badge: "Evidence" },
      { to: "/design-review", label: "Design Review", badge: "Evidence" },
      { to: "/workspace", label: "Workspace Execution", badge: "Evidence" },
      { to: "/mini-delivery", label: "Mini Delivery Pilot", badge: "Evidence" },
      {
        to: "/delivery-package",
        label: "Delivery Package",
        subtitle: "Delivery evidence / package record",
        badge: "Evidence",
      },
      { to: "/regression", label: "Regression", badge: "Read-only" },
      { to: "/cost-llm", label: "Cost / LLM", badge: "Read-only" },
      { to: "/runtime", label: "Runtime Baseline", badge: "Read-only" },
      { to: "/identity", label: "Identity Posture", badge: "Read-only" },
      { to: "/secrets", label: "Secret Posture", badge: "Read-only" },
      { to: "/security", label: "Security", badge: "Read-only" },
      { to: "/metrics", label: "Operational Metrics", badge: "Read-only" },
      { to: "/sandbox-github", label: "Sandbox GitHub", badge: "Read-only" },
      { to: "/release-governance", label: "Release Governance", badge: "Read-only" },
      { to: "/backup-dr", label: "Backup & DR", badge: "Read-only" },
      { to: "/production-readiness", label: "Production Readiness", badge: "Read-only" },
      { to: "/controlled-rollout-review", label: "Rollout Review", badge: "Read-only" },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    subtitle: "Roles, integrations, and policy",
    items: [
      { to: "/settings/roles-permissions", label: "Roles & Permissions", badge: "Soon" },
      { to: "/settings/identity-session", label: "Identity / Session", badge: "Soon" },
      { to: "/settings/integrations", label: "Integrations", badge: "Soon" },
      { to: "/settings/web-research-sources", label: "Web Research Sources", badge: "Soon" },
      { to: "/settings/approval-policy", label: "Approval Policy", badge: "Soon" },
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
