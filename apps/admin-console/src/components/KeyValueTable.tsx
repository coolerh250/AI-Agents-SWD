import { redact } from "../utils/safety";
import { display, titleCase } from "../utils/format";
import { StatusBadge } from "./StatusBadge";

// Renders an object as a key/value table, redacting secret-like fields and
// dropping chain-of-thought keys before display.
export function KeyValueTable({ data }: { data: Record<string, unknown> | null | undefined }) {
  const safe = redact(data || {});
  const entries = Object.entries(safe);
  if (!entries.length) return <div className="empty">No data available</div>;
  return (
    <table>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <th>{titleCase(k)}</th>
            <td>
              {v && typeof v === "object" ? (
                <pre>{JSON.stringify(v, null, 2)}</pre>
              ) : (
                <StatusBadge value={display(v)} />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
