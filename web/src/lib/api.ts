import { AnalysisReport, type AnalyzeRequest } from "../types/api";

// Empty base routes through Vite's dev proxy (/analyze → localhost:8000).
// Set VITE_API_URL when deploying or when calling a different backend.
const BASE = import.meta.env.VITE_API_URL ?? "";

export async function analyze(req: AnalyzeRequest): Promise<AnalysisReport> {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Analyze failed: ${res.status} ${await res.text()}`);
  }
  const json = await res.json();
  return AnalysisReport.parse(json);
}
