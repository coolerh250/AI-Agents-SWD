import { NavLink } from "react-router-dom";

export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "Executive Overview" },
  { to: "/projects", label: "Projects" },
  { to: "/task-graph", label: "Task Graph" },
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
