# decision-lens

> A composable, observable multi-agent pipeline that turns dense administrative decisions into grounded, citation-checked analysis reports.

**Stack:** LangGraph · LiteLLM · Instructor · Langfuse · Ragas · ChromaDB · FastAPI · React + TanStack Query + shadcn/ui

Provider-agnostic via LiteLLM — works with OpenAI, Anthropic, Vertex AI / Gemini, Bedrock, or any local OpenAI-compatible endpoint by changing one env var.

---

## What this is

A six-agent pipeline — **Intake → Extraction → Retrieval → Reasoning → Critic → Report** — for analyzing administrative decisions (denials, appellate rulings, regulatory letters). Each agent has typed Pydantic schemas at every boundary; an adversarial **Critic** agent validates claims against retrieved citations before any output is emitted; every agent run emits structured trace spans with latency, token cost, and confidence.

Independent portfolio implementation. No production code or proprietary data is included; all sample documents are synthetic.

## Status

🚧 **Phase 0** — schemas + FastAPI skeleton + first synthetic case. The `/analyze` endpoint returns a stubbed report. Phase 1 wires the first real LangGraph node.

See [BUILD.md](./BUILD.md) for the full build order.

## Quickstart

```bash
cp .env.example .env       # add your OPENAI_API_KEY (or Anthropic/Vertex)
docker compose up api      # http://localhost:8000/healthz
```

Hit the stubbed endpoint:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "content-type: application/json" \
  -d "$(jq -n --arg t "$(cat data/sample_cases/case_001_administrative_denial.txt)" '{raw_text: $t}')"
```

## Run tests

```bash
pip install -e ".[dev]"
pytest -q
```

## Architecture (target)

```
Document Input
  → Intake          validate, normalize, classify
  → Extraction      span-grounded structured fields
  → Retrieval       per-issue concurrent corpus lookup
  → Reasoning       cited argument synthesis
  → Critic          adversarial faithfulness audit
  → Report          assembly only (approved findings only)
```

## Privacy

This project uses fully synthetic demo documents (`data/sample_cases/`). It is not affiliated with any government agency or production codebase. All party names, claim numbers, and citations in demo data are fictional.

## License

MIT
