"""CLI entry point for the eval suite.

Usage:
    python scripts/run_evals.py [--cases data/golden_cases.jsonl] [--out evals/results/latest.json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.evals import run_evals  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the decision-lens eval suite.")
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    summary = run_evals(cases_path=args.cases, out_path=args.out)

    print(f"\nEval summary ({summary.case_count} cases)")
    print(f"  pass_rate                   {summary.pass_rate:.1%}")
    print(f"  mean_issue_recall           {summary.mean_issue_recall:.2f}")
    print(f"  mean_citation_grounding     {summary.mean_citation_grounding:.2f}")
    print(f"  mean_required_source_recall {summary.mean_required_source_recall:.2f}")
    print(f"  mean_faithfulness           {summary.mean_faithfulness:.2f}")
    if summary.ragas:
        print("  ragas:")
        for k, v in summary.ragas.items():
            print(f"    {k:24} {v:.2f}")
    print()
    for c in summary.cases:
        flag = "✓" if c.passed else "✗"
        err = f" — {c.error}" if c.error else ""
        print(
            f"  {flag} {c.case_id:8} ir={c.issue_recall:.2f} cg={c.citation_grounding:.2f} "
            f"rsr={c.required_source_recall:.2f} {c.duration_ms}ms{err}"
        )

    return 0 if summary.pass_rate >= 0.6 else 1


if __name__ == "__main__":
    sys.exit(main())
