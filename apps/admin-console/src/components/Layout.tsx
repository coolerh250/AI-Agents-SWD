import type { ReactNode } from "react";
import { Nav } from "./Nav";
import { SafetyStatusBar } from "./SafetyStatusBar";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="layout">
      <header>
        <h1>Admin Console v0</h1>
        <span className="ro" title="No workflow dispatch, resume, or production action is available from this shell.">
          NON-PRODUCTION
        </span>
      </header>
      <SafetyStatusBar />
      <div className="app-shell">
        <Nav />
        <main>{children}</main>
      </div>
    </div>
  );
}
