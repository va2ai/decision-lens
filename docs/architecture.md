# Architecture

This document goes deeper than the README. The README answers "what is this and how do I run it"; this answers "why is it shaped this way".

## The pipeline

```
Document text
   │
   ▼
┌──────────┐   ┌─────────────┐   ┌───────────┐   ┌────────────┐   ┌────────┐   ┌────────┐
│  Intake  │──▶│  Extraction │──▶│ Retrieval │──▶│  Reasoning │──▶│ Critic │──▶│ Report │
└──────────┘   └─────────────┘   └───────────┘   └────────────┘   └────────┘   └────────┘
  hard-abort     soft-fail         soft-fail        soft-fail       hard-abort   always-run
```

Each box is a pure function of its typed input; each arrow is a Pydantic schema (`api/schemas/pipeline.py`); each box opens a `span()` so its latency, status, and metadata land on the trace.

## Why six agents, not one prompt

A single "analyze this document end-to-end" prompt is fast to build and impossible to evaluate. You can't say *which* part of it regressed when a metric drops; you can't swap models on the expensive stage; you can't add a deterministic guard between two phases.

Splitting the pipeline buys four things:

1. **Component-wise evaluation.** Citation grounding is scored against retrieval output, not against the final report. Issue recall is scored against extraction, not the LLM's free-form summary at the end.
2. **Narrow prompts.** Each agent's prompt fits in a single screen. The model has one job per call.
3. **Targeted model selection.** Intake (classification) is fine on a cheap model. Reasoning (synthesis with citations) benefits from a stronger model. `LLM_MODEL` is a single env var — swap globally — but the per-agent prompt structure makes it trivial to add per-agent overrides if needed.
4. **A natural place for non-LLM logic.** Span validation, dangling-citation detection, and post-filters live *between* nodes as deterministic code. They never need a prompt.

## Failure semantics (load-bearing — do not collapse)

The graph in `api/agents/graph.py` distinguishes three policies:

### Hard-abort (intake, critic)

If `intake` fails, downstream agents have no document classification and no normalized text — every later stage would produce garbage. If `critic` fails, we cannot honestly distinguish grounded findings from hallucinated ones — the whole faithfulness story collapses. So both raise out of `run_analysis_traced()` and surface as HTTP 500. Failing loudly is correct here.

### Soft-fail (extraction, retrieval, reasoning)

These nodes catch their own exception, set `ctx.poisoned = True`, append a structured warning to `pipeline_warnings`, and let the graph continue.

The `poisoned` flag is *consulted* by the Critic — when set, the Critic blocks every finding regardless of citation grounding. This means a partial pipeline failure produces a report that is honest about its degraded state, not a confident report built on missing evidence.

Why these three and not the others? Because failure here is *recoverable in the sense that the report should still exist*: if retrieval times out on one corpus, the report can say "no citations retrieved, all findings blocked by Critic" instead of returning a 500 that leaves the user with nothing to see.

### Always-run (report)

The Report agent does *no LLM call*. It is pure assembly: take the `IntakeOutput`, the `ExtractionOutput`, the surviving `ReasoningFinding`s, the `CriticOutput`, and the accumulated `pipeline_warnings`, and produce an `AnalysisReport`. This is what makes the soft-fail policy actually useful — there's always a coherent (possibly degraded) report at the end.

## The two-layer Critic

`api/agents/critic.py` runs two stages:

### Stage 1: Deterministic guard (no LLM)

```python
def _deterministic_dangling_check(findings, references):
    valid_ids = {ref.source_id for ref in references}
    blocks = []
    for i, finding in enumerate(findings):
        dangling = [sid for sid in finding.supporting_source_ids if sid not in valid_ids]
        if dangling:
            blocks.append(CriticFlag(
                finding_index=i,
                severity="block",
                category="hallucination",
                explanation=f"References sources not in retrieved set: {dangling}",
            ))
    return blocks
```

This runs *before* any LLM call. It costs zero tokens and zero seconds. It catches the single most common failure mode of citation-aware LLMs — the model invents a plausible-looking `[REG-PHANTOM]` and confidently writes a finding around it.

`tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm` passes with `client=None`, proving the guard does its job in the absence of an LLM.

### Stage 2: LLM critic

Findings that survive stage 1 are passed to an Instructor-validated LLM call. The LLM returns `CriticOutput.flags[]` with `severity ∈ {block, warn, info}`. Block-severity flags drop the finding from `approved_finding_indices`.

A defensive filter strips out flags whose `finding_index` is out of range — the LLM occasionally returns indices that referred to findings the deterministic guard already removed.

## Span tracing — contextvar, not state field

`api/observability/tracing.py` exposes `span()` as a context manager that reads the active `Trace` from a `ContextVar`. LangGraph nodes are pure functions of their state shape — threading the trace through `PipelineContext` would invalidate every test fixture and pollute the agent contract with observability plumbing.

The contextvar is set in `run_analysis_traced()` and reset on exit. `TraceStore` is a bounded LRU (256 traces) so a long-running process holds recent spans in memory without a database. Optional Langfuse passthrough activates if `LANGFUSE_PUBLIC_KEY` is set **and** `langfuse` installs cleanly; it never raises into the pipeline.

## Schema-first parity (Pydantic ↔ Zod)

`api/schemas/pipeline.py` is the source of truth. `web/src/types/api.ts` mirrors every model as a Zod schema and `parse()`s on receipt.

This is a discipline, not an automation. When a field is added or renamed, both files change in the same commit. Past divergences caught only by live testing (real bugs, both fixed):

- `Citation.title` (not `source_title`)
- `StrategyRecommendation` uses `issue_index` + `recommended_action` + `rationale` (not `finding_index` + `recommendation`)
- `AnalysisReport` has no `parties` field

The frontend `parse()` call is the runtime trip-wire — a server response that drifted from the Zod schema crashes the page with a useful error instead of rendering subtly wrong data.

## Provider abstraction

`api/providers/llm.py` wraps LiteLLM + Instructor. The agent code never imports `openai` or `anthropic` or `google.generativeai` directly — it calls `get_client().chat(...)` and lets LiteLLM resolve the model string.

Practical consequence: switching from OpenAI to Gemini to Vertex to Bedrock to a self-hosted vLLM endpoint is a single `.env` edit. Per-provider quirks live in one file and are handled at the wrapper layer (see the recent Gemini-compat fix commits).

## Frontend layout

The frontend is intentionally non-fancy:

- **Vite + React 19 + TypeScript + Tailwind v4.**
- **TanStack Query** for the single mutation (`POST /analyze`) and trace fetch.
- **Zod-mirrored types** as described above.
- **5-tab scroll-spy results** in `web/src/components/Tabs.tsx` using `IntersectionObserver`. All sections render simultaneously; the tabs are navigation, not panel switches. This matters: a user reading the Reasoning tab can ctrl-F across the whole report.

## What is intentionally NOT in this project

- **Authn/authz.** Out of scope for a portfolio piece; the API is open. Plug in your favorite middleware if you fork it.
- **Persistent storage.** Traces are in-memory LRU; ChromaDB is embedded-mode against synthetic data. No DB migrations, no Alembic. Adding Postgres is a single afternoon.
- **A queue.** `/analyze` is synchronous. Real production would put requests on a queue and stream results — that's another afternoon.
- **Custom embeddings.** ChromaDB downloads `all-MiniLM-L6-v2` on first call. Good enough for the demo corpus; swap in a real embedding model if you care.

These omissions are deliberate. The point of this repo is to demonstrate the *agent + critic + eval* shape, not to re-implement infrastructure.
