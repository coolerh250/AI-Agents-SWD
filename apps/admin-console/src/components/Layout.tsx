import type { ReactNode } from "react";
import { Nav } from "./Nav";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="layout">
      <header>
        <h1>Admin Console v0</h1>
        <span className="ro" title="Operator actions are disabled in Admin Console v0.">
          READ-ONLY
        </span>
      </header>
      <Nav />
      <main>{children}</main>
    </div>
  );
}
