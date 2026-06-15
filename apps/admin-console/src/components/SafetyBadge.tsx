import { StatusBadge } from "./StatusBadge";

export function SafetyBadge({ result }: { result: unknown }) {
  return (
    <span className="safety-badge">
      Safety: <StatusBadge value={result} />
    </span>
  );
}
