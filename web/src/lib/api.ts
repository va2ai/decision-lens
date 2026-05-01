import {
  AnalysisResponse,
  TraceView,
  type AnalyzeRequest,
} from "../types/api";

// Empty base routes through Vite's dev proxy (/analyze + /traces -> localhost:8000).
// Set VITE_API_URL when deploying or when calling a different backend.
const BASE = import.meta.env.VITE_API_URL ?? "";

export async function analyze(req: AnalyzeRequest): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text: req.text }),
  });
  if (!res.ok) {
    throw new Error(`Analyze failed: ${res.status} ${await res.text()}`);
  }
  return AnalysisResponse.parse(await res.json());
}

export async function fetchTrace(runId: string): Promise<TraceView> {
  const res = await fetch(`${BASE}/traces/${encodeURIComponent(runId)}`);
  if (!res.ok) {
    throw new Error(`Trace fetch failed: ${res.status} ${await res.text()}`);
  }
  return TraceView.parse(await res.json());
}
