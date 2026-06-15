import { statusTone } from "../utils/status";
import { display } from "../utils/format";

export function StatusBadge({ value }: { value: unknown }) {
  const tone = statusTone(value);
  return <span className={`badge b-${tone}`}>{display(value)}</span>;
}
