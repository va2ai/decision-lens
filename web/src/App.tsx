import { useState } from "react";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ResultsPage } from "./pages/ResultsPage";
import type { AnalysisResponse } from "./types/api";

export default function App() {
  const [response, setResponse] = useState<AnalysisResponse | null>(null);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
      {response ? (
        <ResultsPage
          report={response.report}
          runId={response.run_id}
          onReset={() => setResponse(null)}
        />
      ) : (
        <AnalyzePage onComplete={setResponse} />
      )}
    </div>
  );
}
