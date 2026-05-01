import { useQuery } from "@tanstack/react-query";
import { fetchTrace } from "../lib/api";
import type { SpanView } from "../types/api";

const STATUS_DOT: Record<SpanView["status"], string> = {
  ok: "bg-emerald-500",
  error: "bg-rose-500",
  running: "bg-amber-500 animate-pulse",
};

function fmtMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1) return `${ms.toFixed(2)}ms`;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function AgentTimeline({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["trace", runId],
    queryFn: () => fetchTrace(runId),
    enabled: !!runId,
  });

  if (isLoading) {
    return <p className="text-sm text-zinc-500">Loading trace…</p>;
  }
  if (error) {
    return (
      <p className="text-sm text-rose-700">
        Trace unavailable: {(error as Error).message}
      </p>
    );
  }
  if (!data) return null;

  const totalMs = data.duration_ms ?? 0;
  const startBase = data.started_at;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-xs text-zinc-500">
        <span>
          run <span className="font-mono text-zinc-700">{data.run_id}</span>
        </span>
        <span>
          total <span className="font-mono tabular-nums text-zinc-700">{fmtMs(totalMs)}</span>
        </span>
      </div>
      <ol className="space-y-1.5">
        {data.spans.map((s, i) => {
          const offsetPct = totalMs ? ((s.started_at - startBase) * 1000 * 100) / totalMs : 0;
          const widthPct = totalMs && s.duration_ms ? (s.duration_ms * 100) / totalMs : 0;
          return (
            <li key={i} className="text-xs">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${STATUS_DOT[s.status]}`} />
                <span className="w-20 font-medium text-zinc-700">{s.name}</span>
                <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100">
                  <div
                    className={`absolute h-full rounded-full ${
                      s.status === "error" ? "bg-rose-400" : "bg-blue-400"
                    }`}
                    style={{
                      left: `${offsetPct}%`,
                      width: `${Math.max(widthPct, 0.5)}%`,
                    }}
                  />
                </div>
                <span className="w-14 text-right font-mono tabular-nums text-zinc-500">
                  {fmtMs(s.duration_ms)}
                </span>
              </div>
              {Object.keys(s.metadata).length > 0 && (
                <div className="ml-24 mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-zinc-500">
                  {Object.entries(s.metadata).map(([k, v]) => (
                    <span key={k} className="font-mono">
                      {k}={String(v)}
                    </span>
                  ))}
                </div>
              )}
              {s.error && (
                <div className="ml-24 mt-1 font-mono text-rose-700">{s.error}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
