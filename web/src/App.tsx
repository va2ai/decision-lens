import { useState } from "react";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ResultsPage } from "./pages/ResultsPage";
import { EvalDashboard } from "./components/EvalDashboard";
import type { AnalysisResponse } from "./types/api";

type View =
  | { kind: "analyze" }
  | { kind: "results"; response: AnalysisResponse }
  | { kind: "evals" };

export default function App() {
  const [view, setView] = useState<View>({ kind: "analyze" });

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
      {view.kind === "analyze" && (
        <AnalyzePage
          onComplete={(response) => setView({ kind: "results", response })}
          onShowEvals={() => setView({ kind: "evals" })}
        />
      )}
      {view.kind === "results" && (
        <ResultsPage
          report={view.response.report}
          runId={view.response.run_id}
          onReset={() => setView({ kind: "analyze" })}
        />
      )}
      {view.kind === "evals" && (
        <EvalDashboard onClose={() => setView({ kind: "analyze" })} />
      )}
    </div>
  );
}
