import { EmptyState } from "./EmptyState";

type Dict = Record<string, unknown>;

// Formats a cell value for read-only display. Objects are JSON-stringified;
// null/undefined/empty render as an em dash. No raw code or secrets pass through
// here -- callers only pass shaped, secret-safe endpoint fields.
export function fmtCell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// Read-only table for a list of shaped records. Renders a labelled empty state
// (distinct from an error) when there are no rows.
export function EvidenceTable({
  rows,
  cols,
  empty,
}: {
  rows: Dict[];
  cols: string[];
  empty?: string;
}) {
  if (!rows || rows.length === 0) return <EmptyState message={empty || "No records yet"} />;
  return (
    <table>
      <thead>
        <tr>
          {cols.map((c) => (
            <th key={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c) => (
              <td key={c}>{fmtCell(r[c])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
