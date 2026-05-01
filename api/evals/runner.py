"""Eval runner — runs the pipeline against golden cases and scores results.

Metrics computed per case (deterministic, no LLM required):
  - issue_recall: did extraction surface at least one issue matching expected keywords?
  - decision_match: does the surfaced decision match the expected decision?
  - citation_grounding: % of finding source_ids that resolved against retrieved sources
  - required_source_recall: % of required source_ids that appeared in citations
  - faithfulness: 1 − (block-severity flag count / max(findings, 1))
  - had_block_flag: did the critic block any finding?

Aggregate:
  - pass rate: per case, pass = (issue_recall AND decision_match AND no block flags)
  - mean per-metric score across all cases

Optional Ragas wrapper activates when `LANGFUSE_PUBLIC_KEY` or `OPENAI_API_KEY` is set
AND `ragas` is installed. Without it, only the deterministic metrics run.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from api.agents.graph import run_analysis_traced
from api.schemas.pipeline import AnalysisReport


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    issue_recall: float
    decision_match: bool
    citation_grounding: float
    required_source_recall: float
    faithfulness: float
    had_block_flag: bool
    duration_ms: float
    error: str | None = None


@dataclass
class EvalSummary:
    started_at: float
    ended_at: float
    pass_rate: float
    case_count: int
    mean_issue_recall: float
    mean_citation_grounding: float
    mean_required_source_recall: float
    mean_faithfulness: float
    cases: list[CaseResult] = field(default_factory=list)
    ragas: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cases"] = [asdict(c) for c in self.cases]
        return d


def load_golden_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _score_case(case: dict[str, Any], report: AnalysisReport) -> CaseResult:
    keywords: list[str] = [k.lower() for k in case.get("expected_issue_keywords", [])]
    issue_text_blob = " ".join(i.issue_text.lower() for i in report.issues)
    if keywords:
        hits = sum(1 for k in keywords if k in issue_text_blob)
        issue_recall = hits / len(keywords)
    else:
        issue_recall = 1.0

    expected_decision = case.get("expected_decision")
    decision_match = (
        expected_decision is None
        or any(i.decision == expected_decision for i in report.issues)
    )

    cited_ids = {c.source_id for c in report.citations}
    finding_ids = [sid for f in report.findings for sid in f.supporting_source_ids]
    if finding_ids:
        grounded = sum(1 for sid in finding_ids if sid in cited_ids)
        citation_grounding = grounded / len(finding_ids)
    else:
        # No findings = nothing to ground. Score as 1.0 to avoid penalizing empty cases.
        citation_grounding = 1.0

    required_ids: list[str] = case.get("required_source_ids", [])
    if required_ids:
        present = sum(1 for sid in required_ids if sid in cited_ids)
        required_source_recall = present / len(required_ids)
    else:
        required_source_recall = 1.0

    block_flags = [f for f in report.critic_flags if f.severity == "block"]
    had_block_flag = bool(block_flags)
    faithfulness = (
        1.0 - (len(block_flags) / max(len(report.findings), 1)) if report.findings else 1.0
    )

    passed = (
        issue_recall >= 0.5
        and decision_match
        and not had_block_flag
        and required_source_recall >= 0.5
    )

    return CaseResult(
        case_id=case["id"],
        passed=passed,
        issue_recall=round(issue_recall, 3),
        decision_match=decision_match,
        citation_grounding=round(citation_grounding, 3),
        required_source_recall=round(required_source_recall, 3),
        faithfulness=round(faithfulness, 3),
        had_block_flag=had_block_flag,
        duration_ms=0.0,  # filled by caller
    )


def _maybe_run_ragas(
    cases: list[dict[str, Any]], reports: list[AnalysisReport]
) -> dict[str, float] | None:
    """Best-effort Ragas pass; returns None if unavailable."""
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LANGFUSE_PUBLIC_KEY")):
        return None
    try:
        from ragas.metrics import faithfulness  # type: ignore
        from ragas import evaluate  # type: ignore
        from datasets import Dataset  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    rows: list[dict[str, Any]] = []
    for case, report in zip(cases, reports, strict=True):
        contexts = [c.passage for c in report.citations]
        answer = " ".join(f.finding_text for f in report.findings) or "no findings"
        rows.append(
            {
                "question": " ".join(case.get("expected_issue_keywords", [])) or "issues?",
                "answer": answer,
                "contexts": contexts or [""],
            }
        )
    try:
        ds = Dataset.from_list(rows)
        scores = evaluate(ds, metrics=[faithfulness])
        return {k: float(v) for k, v in scores.items()}
    except Exception:  # noqa: BLE001
        return None


def run_evals(
    *,
    cases_path: Path | None = None,
    out_path: Path | None = None,
) -> EvalSummary:
    cases_path = cases_path or Path(__file__).resolve().parents[2] / "data" / "golden_cases.jsonl"
    out_path = (
        out_path
        or Path(__file__).resolve().parents[2] / "evals" / "results" / "latest.json"
    )

    cases = load_golden_cases(cases_path)
    started = time.time()
    case_results: list[CaseResult] = []
    reports: list[AnalysisReport] = []

    for case in cases:
        t0 = time.time()
        try:
            report, _trace = run_analysis_traced(case["text"])
            res = _score_case(case, report)
            res.duration_ms = round((time.time() - t0) * 1000, 1)
            reports.append(report)
        except Exception as exc:  # noqa: BLE001
            res = CaseResult(
                case_id=case["id"],
                passed=False,
                issue_recall=0.0,
                decision_match=False,
                citation_grounding=0.0,
                required_source_recall=0.0,
                faithfulness=0.0,
                had_block_flag=False,
                duration_ms=round((time.time() - t0) * 1000, 1),
                error=f"{type(exc).__name__}: {exc}",
            )
        case_results.append(res)

    n = max(len(case_results), 1)
    summary = EvalSummary(
        started_at=started,
        ended_at=time.time(),
        pass_rate=round(sum(1 for r in case_results if r.passed) / n, 3),
        case_count=len(case_results),
        mean_issue_recall=round(sum(r.issue_recall for r in case_results) / n, 3),
        mean_citation_grounding=round(sum(r.citation_grounding for r in case_results) / n, 3),
        mean_required_source_recall=round(
            sum(r.required_source_recall for r in case_results) / n, 3
        ),
        mean_faithfulness=round(sum(r.faithfulness for r in case_results) / n, 3),
        cases=case_results,
        ragas=_maybe_run_ragas(cases, reports) if reports else None,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2)

    return summary
