import type { ReactNode } from "react";

export function DataCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="card">
      <div className="k">{label}</div>
      <div className="v">{children}</div>
    </div>
  );
}
