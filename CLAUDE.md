# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common commands

```bash
# Backend (Python 3.11+)
python -m venv .venv && source .venv/Scripts/activate    # activate first; tests fail without it
pip install -e ".[dev]"
pytest -q                                                # full suite (~14s with cold ChromaDB warm-up)
pytest tests/test_critic.py -v                           # single file
pytest tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm -v
ruff check api tests scripts                             # lint
uvicorn api.main:app --reload --port 8000

# Eval suite — exits non-zero if pass_rate < 60%, writes evals/results/latest.json
python scripts/run_evals.py

# Frontend (Node 22 — Vite 8 needs node:util.stripVTControlCharacters)
cd web && npm install && npm run dev                     # http://localhost:5173, proxies /analyze /traces /evals
cd web && npm run build                                  # tsc -b && vite build
cd web && npm run lint
```

When the API is running, hit `http://localhost:8000/docs` for Swagger.

## Architecture

Six-agent DAG: **Intake → Extraction → Retrieval → Reasoning → Critic → Report**, wired in `api/agents/graph.py`. Each agent has its own module under `api/agents/`, a typed Pydantic schema at every boundary (`api/schemas/pipeline.py`), and a contextvar-recorded span on the active `Trace`.

### Failure semantics — load-bearing, do not collapse

- **Hard-abort** in `intake` and `critic`: exception bubbles out of `run_analysis_traced()` as HTTP 500. The report would be uninterpretable without these.
- **Soft-fail** in `extraction`, `retrieval`, `reasoning`: the node catches its own exception, sets `ctx.poisoned=True`, appends a warning, and the graph continues. The Critic respects `poisoned` by blocking every finding.
- **Always-run** `report`: assembly only — no LLM call — so it produces a coherent (degraded) report from a poisoned context and propagates accumulated `pipeline_warnings`.

### Two-layer Critic — `api/agents/critic.py`

1. **Deterministic guard (no LLM, runs first).** Any finding whose `supporting_source_ids` includes an id absent from `RetrievalOutput.references` is auto-blocked with a `hallucination` flag. The hallucination-injection test (`tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm`) is the load-bearing assertion — it passes with `client=None`. Don't move this guard behind the LLM.
2. **LLM critic.** Findings that pass the guard go through Instructor for `severity ∈ {block, warn, info}` flags. Out-of-range LLM-returned indices are filtered (the LLM occasionally targets findings the deterministic guard already removed).

### Span tracing — contextvar, not state field

`api/observability/tracing.py` exposes `span()` as a context manager that reads the active `Trace` from a `ContextVar`. LangGraph nodes are pure functions of their state shape — threading the trace through `PipelineContext` would invalidate every test fixture. The contextvar is set in `run_analysis_traced()` and reset on exit. `TraceStore` is a bounded LRU (256). Optional Langfuse passthrough activates if `LANGFUSE_PUBLIC_KEY` is set **and** `langfuse` installs cleanly; never raises into the pipeline.

### Schema-first parity — Pydantic ↔ Zod

`api/schemas/pipeline.py` is the source of truth. `web/src/types/api.ts` mirrors every model as a Zod schema and `parse()`s on receipt. **When you add or rename a field, both files change in the same commit.** Past divergences caught only by live testing (real bugs, both fixed): `Citation.title` (not `source_title`); `StrategyRecommendation` uses `issue_index` + `recommended_action` + `rationale` (not `finding_index` + `recommendation`); `AnalysisReport` has no `parties` field.

### Eval scoring is deterministic by design

`api/evals/runner.py` computes `issue_recall`, `decision_match`, `citation_grounding`, `required_source_recall`, `faithfulness` without an LLM call so the suite runs in CI without an API key. The Ragas wrapper activates only when `OPENAI_API_KEY` or `LANGFUSE_PUBLIC_KEY` is set **and** `pip install -e ".[evals]"` was run. Don't replace the deterministic scorer with Ragas — keep both.

## Conventions

- **No bare `os.getenv` in agent code.** All config flows through `api/config.py` `Settings` (pydantic-settings). Tests can override via env vars.
- **`get_client()` and `get_store()` are import-time global factories** in `api/providers/llm.py` and `api/retrieval/store.py`. Tests `monkeypatch.setattr(graph_mod, "get_client", lambda: stub)` to inject — see `tests/test_pipeline_e2e.py` for the pattern. The deterministic `StubStore` returns the same fixed references every time so reasoning-stub source_ids match what the post-filter expects.
- **Schema + normalizer pair.** When the LLM produces an Instructor-validated output, validate the Pydantic schema first, then run any deterministic post-filter (e.g. `extraction.validate_spans()` drops issues whose `source_span` is out-of-range; `reasoning.run()` drops findings citing unknown source_ids). Don't push these into the prompt — keep them deterministic.
- **Frontend tabs are scroll-spy, not panel-switch.** `web/src/components/Tabs.tsx` uses `IntersectionObserver` and `scrollIntoView`. All sections render simultaneously. Don't regress to conditional rendering.

## Gotchas

- **Activate `.venv` first.** The system Python doesn't have the deps installed; `pytest` outside the venv errors with `ModuleNotFoundError: langgraph`.
- **Node 22 required for the frontend.** Vite 8 imports `stripVTControlCharacters` from `node:util`, added in Node 20.12. Older nvm-windows defaults (Node 15/18) crash at install. On Windows: `nvm use 22.22.2` then verify with `node -v` in a fresh shell — `nvm use` doesn't update PATH in the current bash session.
- **`GOOGLE_API_KEY` overrides `GEMINI_API_KEY`.** LiteLLM resolves `gemini/*` model strings against `GEMINI_API_KEY`, but the underlying `@google/genai` SDK prefers `GOOGLE_API_KEY` if set. Clear or align them when debugging.
- **ChromaDB cold start.** First call to `get_store().ensure_loaded()` downloads the `all-MiniLM-L6-v2` ONNX model (~80 MB) to `~/.cache/chroma`. The FastAPI lifespan hook warms it at startup so `/analyze` doesn't pay the cost on the first request.
- **`scripts/run_evals.py` runs the full pipeline against five golden cases.** Without an LLM key the pipeline hard-aborts in intake; the runner records each as `error` and the suite exits non-zero. The deterministic *scorer* runs without an LLM (`tests/test_evals.py` exercises `_score_case` directly) — that's separate from running the pipeline.
- **`.env` is gitignored.** `.env.example` documents the providers; `LLM_MODEL` decides which one LiteLLM uses (`gpt-4o-mini`, `claude-sonnet-4-5`, `gemini/gemini-2.5-flash`, `vertex_ai/gemini-2.5-pro`, etc.).
- **`run_analysis()` is the legacy single-return entry point.** New code should call `run_analysis_traced()` to get back `(report, trace)`. The HTTP layer needs the trace for `run_id`.
