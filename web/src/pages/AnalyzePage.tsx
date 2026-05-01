import { useState, type ChangeEvent, type FormEvent } from "react";
import { useAnalyze } from "../hooks/useAnalyze";
import type { AnalysisResponse } from "../types/api";

export function AnalyzePage({
  onComplete,
  onShowEvals,
}: {
  onComplete: (response: AnalysisResponse) => void;
  onShowEvals: () => void;
}) {
  const [text, setText] = useState("");
  const mutation = useAnalyze();

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    mutation.mutate({ text }, { onSuccess: onComplete });
  }

  const isPending = mutation.isPending;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div className="text-xs font-medium uppercase tracking-wide text-blue-600">
            Decision Lens
          </div>
          <button
            type="button"
            onClick={onShowEvals}
            className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
          >
            Eval suite →
          </button>
        </div>
        <h1 className="mt-1 text-3xl font-semibold text-zinc-900">
          Analyze a decision document
        </h1>
        <p className="mt-2 text-zinc-600">
          Paste a denial, appeal, or examination report. The pipeline extracts issues,
          retrieves cited authority, and runs an adversarial critic before producing a
          grounded report.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-2 flex items-center justify-between text-sm font-medium text-zinc-700">
            <span>Document text</span>
            <input
              type="file"
              accept=".txt,.md"
              onChange={handleFile}
              className="text-xs text-zinc-500 file:mr-2 file:rounded-md file:border-0 file:bg-zinc-100 file:px-2 file:py-1 file:text-xs file:font-medium hover:file:bg-zinc-200"
            />
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={16}
            placeholder="Paste the decision text here, or upload a .txt file…"
            className="w-full rounded-md border border-zinc-300 bg-white p-3 font-mono text-sm text-zinc-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={isPending}
          />
          <p className="mt-1 text-xs text-zinc-500">{text.length} characters</p>
        </div>

        {mutation.isError && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            <div className="font-medium">Analysis failed</div>
            <div className="font-mono text-xs">
              {(mutation.error as Error).message}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={isPending || !text.trim()}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300"
          >
            {isPending ? (
              <>
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Running pipeline…
              </>
            ) : (
              "Analyze"
            )}
          </button>
          {isPending && (
            <span className="text-xs text-zinc-500">
              Intake → Extraction → Retrieval → Reasoning → Critic → Report
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
