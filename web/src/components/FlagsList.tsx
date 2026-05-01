import type { CriticFlag } from "../types/api";

const SEV: Record<CriticFlag["severity"], string> = {
  block: "bg-rose-100 text-rose-800 border-rose-300",
  warn: "bg-amber-100 text-amber-800 border-amber-300",
  info: "bg-sky-100 text-sky-800 border-sky-300",
};

export function FlagsList({ flags }: { flags: CriticFlag[] }) {
  if (flags.length === 0) {
    return <p className="text-sm text-zinc-500">No critic flags. Pipeline output is clean.</p>;
  }
  return (
    <ul className="space-y-2">
      {flags.map((f, i) => (
        <li
          key={i}
          className="rounded-md border border-zinc-200 bg-white p-3 text-sm"
        >
          <div className="flex items-center gap-2">
            <span
              className={`rounded-md border px-2 py-0.5 text-xs font-semibold uppercase ${SEV[f.severity]}`}
            >
              {f.severity}
            </span>
            <span className="font-mono text-xs text-zinc-500">{f.flag_type}</span>
            <span className="text-xs text-zinc-500">→ finding {f.target_index}</span>
          </div>
          <p className="mt-1 text-zinc-700">{f.explanation}</p>
        </li>
      ))}
    </ul>
  );
}
