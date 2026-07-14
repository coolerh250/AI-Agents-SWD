import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { NavGroupConfig, NavItem } from "./Nav";

function itemMatchesPath(item: NavItem, pathname: string): boolean {
  if (item.end) return pathname === item.to;
  if (item.to === "/") return pathname === "/";
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

export function NavGroup({ group }: { group: NavGroupConfig }) {
  const location = useLocation();
  const isActiveGroup = useMemo(
    () => group.items.some((item) => itemMatchesPath(item, location.pathname)),
    [group.items, location.pathname],
  );
  const [expanded, setExpanded] = useState(group.defaultExpanded ?? true);

  useEffect(() => {
    if (isActiveGroup) setExpanded(true);
  }, [isActiveGroup]);

  const open = group.collapsible ? expanded : true;
  const contentId = `nav-group-${group.id}-items`;

  return (
    <section className="nav-group" data-testid={`nav-group-${group.id}`}>
      {group.collapsible ? (
        <button
          type="button"
          className="nav-group-toggle"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setExpanded((current) => !current)}
        >
          <span>{group.label}</span>
          <span aria-hidden="true">{open ? "-" : "+"}</span>
        </button>
      ) : (
        <div className="nav-group-title">{group.label}</div>
      )}
      {open && (
        <div id={contentId} className="nav-group-items">
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end ?? item.to === "/"}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      )}
    </section>
  );
}
