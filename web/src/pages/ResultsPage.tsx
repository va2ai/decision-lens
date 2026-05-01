import type { AnalysisReport } from "../types/api";
import { CitationBadge } from "../components/CitationBadge";
import { EvidenceList } from "../components/EvidenceList";
import { FindingsPanel } from "../components/FindingsPanel";
import { FlagsList } from "../components/FlagsList";
import { IssueCard } from "../components/IssueCard";
import { StrategyPanel } from "../components/StrategyPanel";
import { Tabs } from "../components/Tabs";

const TAB_IDS = {
  issues: "issues",
  evidence: "evidence",
  findings: "findings",
  strategy: "strategy",
  flags: "flags",
} as const;

export function ResultsPage({
  report,
  onReset,
}: {
  report: AnalysisReport;
  onReset: () => void;
}) {
  const tabs = [
    { id: TAB_IDS.issues, label: "Issues", count: report.issues.length },
    { id: TAB_IDS.evidence, label: "Evidence", count: report.evidence.length },
    { id: TAB_IDS.findings, label: "Findings", count: report.findings.length },
    { id: TAB_IDS.strategy, label: "Strategy", count: report.strategy.length },
    { id: TAB_IDS.flags, label: "Flags", count: report.critic_flags.length },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Analysis Report
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-zinc-900">
            {report.doc_type.replace(/_/g, " ")}
          </h1>
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
            <span>
              Confidence{" "}
              <span className="font-mono tabular-nums text-zinc-700">
                {Math.round(report.overall_confidence * 100)}%
              </span>
            </span>
            <span>
              Faithfulness{" "}
              <span className="font-mono tabular-nums text-zinc-700">
                {Math.round(report.faithfulness_score * 100)}%
              </span>
            </span>
            <span className="font-mono">{report.prompt_version}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          New analysis
        </button>
      </header>

      {report.pipeline_warnings.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <div className="font-medium">Pipeline warnings</div>
          <ul className="mt-1 list-disc pl-5">
            {report.pipeline_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <Tabs tabs={tabs} />

      <section id={TAB_IDS.issues} className="scroll-mt-20 space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900">Issues</h2>
        {report.issues.length === 0 ? (
          <p className="text-sm text-zinc-500">No issues extracted.</p>
        ) : (
          <div className="space-y-3">
            {report.issues.map((issue, i) => (
              <IssueCard key={i} issue={issue} index={i} />
            ))}
          </div>
        )}
      </section>

      <section id={TAB_IDS.evidence} className="scroll-mt-20 space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900">Evidence</h2>
        <EvidenceList items={report.evidence} />
      </section>

      <section id={TAB_IDS.findings} className="scroll-mt-20 space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900">Findings</h2>
        <FindingsPanel findings={report.findings} citations={report.citations} />
        {report.citations.length > 0 && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Retrieved sources
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {report.citations.map((c) => (
                <CitationBadge
                  key={c.source_id}
                  sourceId={c.source_id}
                  authorityType={c.authority_type}
                />
              ))}
            </div>
          </div>
        )}
      </section>

      <section id={TAB_IDS.strategy} className="scroll-mt-20 space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900">Strategy</h2>
        <StrategyPanel items={report.strategy} />
      </section>

      <section id={TAB_IDS.flags} className="scroll-mt-20 space-y-3 pb-20">
        <h2 className="text-lg font-semibold text-zinc-900">Critic flags</h2>
        <FlagsList flags={report.critic_flags} />
      </section>
    </div>
  );
}
