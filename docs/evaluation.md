# Evaluation notes

## Two scorers, side by side

There are two evaluation paths in this repo:

1. **A deterministic scorer** — five metrics, no LLM call, always runs.
2. **An optional Ragas wrapper** — LLM-as-judge faithfulness, runs only when both an LLM key and the `evals` extra are present.

Both are kept. The deterministic scorer is what CI runs; the Ragas wrapper is a sanity check when an LLM is available locally. They measure overlapping but not identical things, and disagreement between them is a useful signal.

## The five deterministic metrics

Defined in `api/evals/runner.py::_score_case` and exercised in isolation by `tests/test_evals.py::test_score_case` (no LLM needed).

| Metric | Formula | What it catches |
|---|---|---|
| `issue_recall` | `len(found_keywords ∩ expected_keywords) / len(expected_keywords)` | Extraction missed an issue the labeled case calls out |
| `decision_match` | `extracted_decision == expected_decision` (1.0 / 0.0) | Intake misclassified the document |
| `citation_grounding` | `len(grounded_source_ids) / len(all_finding_source_ids)` | A finding cites a source the retriever never returned (should always be 1.0 if the three-layer guard works) |
| `required_source_recall` | `len(retrieved_required ∩ expected_required) / len(expected_required)` | Retrieval missed a source the labeled case considers necessary |
| `faithfulness` | `1 − blocked_findings / total_findings` | The Critic had to block findings (high blocking rate means upstream stages are producing hallucinations) |

All five are computed per case, then averaged across the suite. A case **passes** if all five are ≥ 0.6 (configurable). The suite **passes** if pass-rate ≥ 60% — `scripts/run_evals.py` exits non-zero otherwise so CI can gate on it.

## Why these five

They were chosen because together they describe the system's correctness without leaning on an LLM judge:

- `issue_recall` catches *under-extraction* (the model summarizes but misses things).
- `decision_match` catches *miscategorization* (calling a denial a remand).
- `citation_grounding` is the central faithfulness property — it should be 1.0 in every passing case because the three concentric guards (schema, post-filter, Critic) all enforce it. Anything below 1.0 means something escaped all three.
- `required_source_recall` catches *retrieval gaps* — labelled cases name the regulations a competent reviewer would cite; if retrieval doesn't surface them, the downstream reasoning can't either.
- `faithfulness` catches *upstream hallucination rate* — if reasoning is producing findings the Critic has to block, we want that number visible.

What they intentionally don't measure: the *quality* of the reasoning narrative, the *helpfulness* of the recommendations, the *tone* of the summary. Those need humans or an LLM judge — see the Ragas section below.

## The golden cases

`data/golden_cases.jsonl` — five labeled synthetic cases. Each entry:

```json
{
  "id": "gc_001",
  "doc_type": "administrative_denial",
  "expected_issue_keywords": ["respiratory", "service connection"],
  "expected_decision": "denied",
  "required_source_ids": ["REG-3.159"],
  "text": "Demo Review Board\nClaim ID: GC-001\n\nDecision: ..."
}
```

The cases are intentionally synthetic. They use fictional party names ("Demo"), fictional regulation numbers (`REG-3.159`, `REG-5107`, etc.), and fictional case names ("Demo v. Secretary"). The shape of the documents mirrors real administrative-decision style, but no real claim, claimant, or agency is referenced.

Five cases is small. The shape of the suite is the contribution — adding more cases is a one-line append per case. The metric set and the pass-rate gate stay the same.

## The optional Ragas wrapper

Activates when:

- An LLM key is set (`OPENAI_API_KEY` or `LANGFUSE_PUBLIC_KEY`), and
- `pip install -e ".[evals]"` has been run (pulls in `ragas` and `datasets`).

When active, the runner invokes Ragas's `faithfulness` LLM-as-judge metric and surfaces it alongside the deterministic metrics in the dashboard. Otherwise, the Ragas column is omitted.

This is deliberately *additive* — the deterministic scorer is never replaced. Reasons:

- **CI runs without keys.** A CI pipeline that depends on an LLM is slow, expensive, and breaks when the API does.
- **LLM judges drift.** Ragas's faithfulness model can change between releases, and the score can shift without the underlying system changing. The deterministic metrics are reproducible bit-for-bit.
- **The two measure different things.** Ragas asks "is this generated answer entailed by the provided context?". The deterministic `citation_grounding` asks "are the cited source ids actually in the retrieved set?". A finding can pass the second and fail the first (cited the right doc, claimed too much) — that disagreement is information.

## Running the evals

```bash
# Deterministic scorer only — no LLM key needed
pytest tests/test_evals.py -v                        # exercises _score_case directly

# Full suite — runs the actual pipeline against five cases
echo "OPENAI_API_KEY=sk-..." > .env
python scripts/run_evals.py                          # writes evals/results/latest.json
```

Output schema (`evals/results/latest.json`):

```json
{
  "suite_pass_rate": 0.8,
  "cases": [
    {
      "id": "gc_001",
      "passed": true,
      "metrics": {
        "issue_recall": 1.0,
        "decision_match": 1.0,
        "citation_grounding": 1.0,
        "required_source_recall": 1.0,
        "faithfulness": 1.0,
        "ragas_faithfulness": 0.91     // only present when Ragas active
      }
    }
  ]
}
```

The dashboard at `web/src/components/EvalDashboard.tsx` reads `GET /evals/latest` and renders per-case rows.

## What a regression looks like

If a change to a prompt or agent code regresses correctness, the deterministic metrics catch it in this order:

1. **`faithfulness` drops** → reasoning is producing hallucinations the Critic is having to block. The block reasons in `critic_flags[]` say what kind.
2. **`citation_grounding` drops below 1.0** → something escaped all three guards. This should never happen; if it does, look at which guard regressed in `tests/test_critic.py` and `tests/test_reasoning.py`.
3. **`required_source_recall` drops** → retrieval changed (embedding model, corpus, query construction).
4. **`issue_recall` drops** → extraction missed things. Often a prompt regression.
5. **`decision_match` drops** → intake misclassified. Cheapest fix: tighten the classifier prompt.

Tracking these per-case over time is what `GET /evals/latest` and the EvalDashboard exist for.
