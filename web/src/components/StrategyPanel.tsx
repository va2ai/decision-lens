import type { StrategyRecommendation } from "../types/api";

const PRIORITY: Record<StrategyRecommendation["priority"], string> = {
  critical: "bg-rose-600 text-white",
  important: "bg-amber-500 text-white",
  optional: "bg-zinc-400 text-white",
};

export function StrategyPanel({ items }: { items: StrategyRecommendation[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-zinc-500">No strategy recommendations.</p>;
  }
  return (
    <ol className="space-y-3">
      {items.map((s, i) => (
        <li
          key={i}
          className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm"
        >
          <span
            className={`mt-0.5 inline-flex h-6 items-center rounded-full px-2 text-xs font-semibold uppercase tracking-wide ${PRIORITY[s.priority]}`}
          >
            {s.priority}
          </span>
          <p className="text-sm text-zinc-800">{s.recommendation}</p>
        </li>
      ))}
    </ol>
  );
}
