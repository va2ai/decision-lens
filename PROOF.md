# PROOF — what actually works

This file is the "show me, don't tell me" companion to the README. Every claim below maps to a runnable artifact in this repo.

## 1. The pipeline runs end-to-end without an LLM key — and so does the test suite

The test suite stubs the LLM client and the vector store, then runs the full six-agent DAG. **48 tests pass in ~14 seconds** on a cold checkout.

```bash
pip install -e ".[dev]"
pytest -q
```

What this proves:

- The graph wiring in `api/agents/graph.py` is correct: every node receives the upstream context it expects, and the soft-fail / hard-abort policy actually fires.
- The schema contracts in `api/schemas/pipeline.py` reject malformed agent outputs at the Pydantic layer before they reach downstream nodes.
- The Critic's deterministic guard catches injected hallucinated citations *without* an LLM (see §3).

## 2. The Critic blocks hallucinated citations deterministically

`tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm` is the load-bearing assertion. It:

1. Constructs a `ReasoningFinding` whose `supporting_source_ids` references `REG-PHANTOM` — a source the retrieval node never returned.
2. Runs the Critic with `client=None` (no LLM available).
3. Asserts that the finding is `not in approved_finding_indices` and that a `hallucination` flag with `severity == "block"` was attached.

This means: even if the LLM critic is unreachable, mis-configured, or rate-limited, a hallucinated citation cannot reach the final report. The deterministic guard in `api/agents/critic.py::_deterministic_dangling_check` runs first by design.

## 3. There are three concentric layers preventing ungrounded claims

| Layer | Where | Proof |
|---|---|---|
| 1. Pydantic schema | `api/schemas/pipeline.py` — `ReasoningFinding.supporting_source_ids: list[str] = Field(min_length=1)` | `tests/test_schemas.py::test_schema_rejects_finding_without_any_citation` |
| 2. Reasoning post-filter | `api/agents/reasoning.py` drops findings whose source_ids aren't in `RetrievalOutput.references` | `tests/test_reasoning.py` (citation-grounding test) |
| 3. Critic deterministic guard | `api/agents/critic.py::_deterministic_dangling_check` runs before the LLM critic | `tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm` |

A hallucinated citation has to defeat *all three* to ship in a report. Each is tested independently.

## 4. Soft-fail and hard-abort actually differ in behavior

`api/agents/graph.py` distinguishes node failure modes:

- **Hard-abort** (`intake`, `critic`) — exception bubbles out as HTTP 500. The report would be uninterpretable without these.
- **Soft-fail** (`extraction`, `retrieval`, `reasoning`) — the node catches its own exception, sets `ctx.poisoned=True`, appends a warning. The Critic then blocks every finding.
- **Always-run** (`report`) — assembly-only, no LLM call, so it produces a coherent (degraded) report from a poisoned context.

Covered by `tests/test_pipeline_e2e.py`.

## 5. The eval suite is deterministic — no LLM needed to score

`api/evals/runner.py` computes five metrics on the report output:

| Metric | What it measures |
|---|---|
| `issue_recall` | fraction of expected keywords surfaced in extracted issues |
| `decision_match` | extracted decision matches the labeled `expected_decision` |
| `citation_grounding` | fraction of finding `source_id`s that resolve against retrieved citations |
| `required_source_recall` | fraction of expected `required_source_ids` that appear in citations |
| `faithfulness` | `1 − blocked_findings / total_findings` |

`scripts/run_evals.py` runs the full pipeline against `data/golden_cases.jsonl` (five labeled cases) and exits non-zero if `pass_rate < 60%`. The deterministic scorer is exercised in isolation by `tests/test_evals.py::test_score_case` — it runs in CI without an API key.

The optional Ragas wrapper activates only when (a) `OPENAI_API_KEY` or `LANGFUSE_PUBLIC_KEY` is set and (b) `pip install -e ".[evals]"` has been run. Both scorers run side-by-side when available — see `docs/eval-notes.md`.

## 6. Span tracing is real — every run produces a trace

Every node opens a `span()` context manager via `contextvars` (so pure-function LangGraph nodes don't have to thread the trace through state). After any `/analyze` call, `GET /traces/{run_id}` returns the spans with durations, statuses, and metadata.

Covered by `tests/test_tracing.py`.

## 7. Frontend and backend share one schema source of truth

`api/schemas/pipeline.py` is mirrored as Zod schemas in `web/src/types/api.ts`. The frontend `parse()`s every API response — drift between the two surfaces immediately at runtime or build time. Past divergences caught only by live testing (and since fixed): `Citation.title` vs `source_title`, `StrategyRecommendation` field names, `AnalysisReport.parties` (didn't exist).

## How to verify yourself

```bash
# Backend correctness
pip install -e ".[dev]"
pytest -q                                                                  # 48/48 green

# Eval suite (needs an LLM key, otherwise records 5x "error" and exits 1)
echo "OPENAI_API_KEY=sk-..." > .env
python scripts/run_evals.py                                                # writes evals/results/latest.json

# UI on real data
uvicorn api.main:app --reload --port 8000 &
cd web && npm install && npm run dev                                       # http://localhost:5173
```

Or, if no LLM key is available, set `DEMO_MODE=1` in `.env` to exercise the live frontend against a deterministic stub — see the README "How we prevent ungrounded claims" section for what this does and doesn't prove.
