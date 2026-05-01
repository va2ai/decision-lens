import type { DocumentIssue } from "../types/api";

const DECISION_COLOR: Record<DocumentIssue["decision"], string> = {
  granted: "text-emerald-700 bg-emerald-50 border-emerald-200",
  denied: "text-rose-700 bg-rose-50 border-rose-200",
  deferred: "text-amber-700 bg-amber-50 border-amber-200",
  remanded: "text-blue-700 bg-blue-50 border-blue-200",
  other: "text-zinc-700 bg-zinc-50 border-zinc-200",
};

export function IssueCard({ issue, index }: { issue: DocumentIssue; index: number }) {
  const pct = Math.round(issue.confidence * 100);
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Issue {index + 1}
          </div>
          <div className="mt-1 text-sm font-medium text-zinc-900">{issue.issue_text}</div>
        </div>
        <span
          className={`whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-semibold ${DECISION_COLOR[issue.decision]}`}
        >
          {issue.decision}
        </span>
      </div>
      {issue.stated_reason && (
        <p className="mt-2 text-sm text-zinc-600">
          <span className="font-medium text-zinc-700">Stated reason: </span>
          {issue.stated_reason}
        </p>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
        <span>Confidence</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100">
          <div
            className="h-full rounded-full bg-blue-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="font-mono tabular-nums">{pct}%</span>
      </div>
    </div>
  );
}
