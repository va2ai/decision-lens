import { useState } from "react";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ResultsPage } from "./pages/ResultsPage";
import type { AnalysisReport } from "./types/api";

export default function App() {
  const [report, setReport] = useState<AnalysisReport | null>(null);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
      {report ? (
        <ResultsPage report={report} onReset={() => setReport(null)} />
      ) : (
        <AnalyzePage onComplete={setReport} />
      )}
    </div>
  );
}
