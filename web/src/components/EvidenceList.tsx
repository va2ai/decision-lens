import type { EvidenceItem } from "../types/api";

const FAVORABILITY: Record<EvidenceItem["favorability"], string> = {
  favorable: "border-l-emerald-500",
  adverse: "border-l-rose-500",
  neutral: "border-l-zinc-400",
  missing: "border-l-amber-500",
};

const FAV_LABEL: Record<EvidenceItem["favorability"], string> = {
  favorable: "Favorable",
  adverse: "Adverse",
  neutral: "Neutral",
  missing: "Missing",
};

export function EvidenceList({ items }: { items: EvidenceItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-zinc-500">No evidence extracted.</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((ev, i) => (
        <li
          key={i}
          className={`rounded-md border border-zinc-200 border-l-4 bg-white p-3 ${FAVORABILITY[ev.favorability]}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm font-medium text-zinc-900">{ev.label}</div>
            <span className="whitespace-nowrap text-xs text-zinc-500">
              {FAV_LABEL[ev.favorability]} · {ev.source_type}
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-600">{ev.description}</p>
        </li>
      ))}
    </ul>
  );
}
