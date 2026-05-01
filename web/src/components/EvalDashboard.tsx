import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

const CaseResult = z.object({
  case_id: z.string(),
  passed: z.boolean(),
  issue_recall: z.number(),
  decision_match: z.boolean(),
  citation_grounding: z.number(),
  required_source_recall: z.number(),
  faithfulness: z.number(),
  had_block_flag: z.boolean(),
  duration_ms: z.number(),
  error: z.string().nullable().optional(),
});

const EvalSummary = z.object({
  started_at: z.number(),
  ended_at: z.number(),
  pass_rate: z.number(),
  case_count: z.number(),
  mean_issue_recall: z.number(),
  mean_citation_grounding: z.number(),
  mean_required_source_recall: z.number(),
  mean_faithfulness: z.number(),
  cases: z.array(CaseResult),
  ragas: z.record(z.string(), z.number()).nullable().optional(),
});
type EvalSummary = z.infer<typeof EvalSummary>;

const BASE = import.meta.env.VITE_API_URL ?? "";

async function fetchEvals(): Promise<EvalSummary> {
  const res = await fetch(`${BASE}/evals/latest`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return EvalSummary.parse(await res.json());
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function Stat({ label, value, large }: { label: string; value: string; large?: boolean }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-white px-3 py-2">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div
        className={`mt-0.5 font-mono tabular-nums text-zinc-900 ${
          large ? "text-2xl font-semibold" : "text-lg"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

export function EvalDashboard({ onClose }: { onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["evals"],
    queryFn: fetchEvals,
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-blue-600">
            Eval suite
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-zinc-900">Latest results</h1>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          Back
        </button>
      </header>

      {isLoading && <p className="text-sm text-zinc-500">Loading…</p>}
      {error && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="font-medium">No eval results yet</div>
          <p className="mt-1">
            Run <code className="rounded bg-amber-100 px-1 font-mono">python scripts/run_evals.py</code>
            {" "}from the project root to generate{" "}
            <code className="rounded bg-amber-100 px-1 font-mono">evals/results/latest.json</code>.
          </p>
          <p className="mt-2 font-mono text-xs">{(error as Error).message}</p>
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Pass rate" value={pct(data.pass_rate)} large />
            <Stat label="Issue recall" value={pct(data.mean_issue_recall)} />
            <Stat label="Citation grounding" value={pct(data.mean_citation_grounding)} />
            <Stat label="Required-source recall" value={pct(data.mean_required_source_recall)} />
            <Stat label="Faithfulness" value={pct(data.mean_faithfulness)} />
          </div>

          {data.ragas && (
            <div className="rounded-md border border-purple-200 bg-purple-50 p-3 text-sm text-purple-900">
              <div className="font-medium">Ragas (LLM-as-judge)</div>
              <div className="mt-1 flex flex-wrap gap-3">
                {Object.entries(data.ragas).map(([k, v]) => (
                  <span key={k} className="font-mono">
                    {k}={pct(v)}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-3 py-2">Case</th>
                  <th className="px-3 py-2">Pass</th>
                  <th className="px-3 py-2">Issue recall</th>
                  <th className="px-3 py-2">Citation grounding</th>
                  <th className="px-3 py-2">Required src</th>
                  <th className="px-3 py-2 text-right">Time</th>
                </tr>
              </thead>
              <tbody>
                {data.cases.map((c) => (
                  <tr key={c.case_id} className="border-t border-zinc-100">
                    <td className="px-3 py-2 font-mono text-xs">{c.case_id}</td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          c.passed
                            ? "text-emerald-700"
                            : c.error
                              ? "text-rose-700"
                              : "text-amber-700"
                        }
                      >
                        {c.passed ? "✓" : c.error ? "✗ err" : "✗"}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono tabular-nums">{pct(c.issue_recall)}</td>
                    <td className="px-3 py-2 font-mono tabular-nums">
                      {pct(c.citation_grounding)}
                    </td>
                    <td className="px-3 py-2 font-mono tabular-nums">
                      {pct(c.required_source_recall)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-zinc-500">
                      {Math.round(c.duration_ms)}ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
