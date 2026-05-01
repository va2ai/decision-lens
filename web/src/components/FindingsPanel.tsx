import type { Citation, ReportFinding } from "../types/api";
import { CitationBadge } from "./CitationBadge";

export function FindingsPanel({
  findings,
  citations,
}: {
  findings: ReportFinding[];
  citations: Citation[];
}) {
  if (findings.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No grounded findings survived the critic. See flags for why.
      </p>
    );
  }
  const byId = new Map(citations.map((c) => [c.source_id, c]));
  return (
    <div className="space-y-4">
      {findings.map((f, i) => (
        <div
          key={i}
          className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Finding {i + 1} · Issue {f.issue_index + 1}
            </div>
            <span className="font-mono text-xs tabular-nums text-zinc-500">
              conf {Math.round(f.confidence * 100)}%
            </span>
          </div>
          <p className="mt-2 text-sm text-zinc-800">{f.finding_text}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {f.supporting_source_ids.map((sid) => {
              const c = byId.get(sid);
              return (
                <CitationBadge
                  key={sid}
                  sourceId={sid}
                  authorityType={c?.authority_type ?? "other"}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
