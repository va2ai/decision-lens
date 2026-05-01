# Build Order

34 commits across 7 phases. Each phase ends with something testable.

---

## Phase 0 — Skeleton (½ day) ✅

- [x] 1. `git init` · `pyproject.toml` (uv) · workspace · Ruff + pytest config · `.gitignore`
- [x] 2. `api/schemas/pipeline.py` — all 9 Pydantic models (the contracts come first)
- [x] 3. `api/main.py` — FastAPI with `POST /analyze` returning a stubbed `AnalysisReport`
- [x] 4. `data/sample_cases/case_001_administrative_denial.txt` — first synthetic case
- [x] 5. `Dockerfile.api` + `docker-compose.yml` + `.env.example`

✅ **Done when:** `docker compose up api` returns a valid (stubbed) report shape.

---

## Phase 1 — One agent end-to-end (1 day)

- [ ] 6. `api/providers/llm.py` — LiteLLM wrapper with retry/timeout
- [ ] 7. `api/prompts/intake_v1.txt`
- [ ] 8. `api/agents/intake.py` using Instructor for structured output
- [ ] 9. `api/agents/graph.py` — LangGraph `StateGraph` with just the Intake node + early return
- [ ] 10. `tests/test_intake.py` — schema validation + classification accuracy

---

## Phase 2 — Full pipeline (2–3 days)

- [ ] 11. Extraction agent + prompt + span-grounding test
- [ ] 12. Retrieval agent + ChromaDB embedded mode + `data/mock_sources/`
- [ ] 13. Reasoning agent + prompt + citation-grounding test
- [ ] 14. Critic agent + prompt + hallucination-injection test
- [ ] 15. Report agent (assembly-only)
- [ ] 16. Wire all 6 nodes in LangGraph with conditional edges
- [ ] 17. End-to-end test on case_001

---

## Phase 3 — Frontend (2 days)

- [ ] 18. `web/` — Vite + React + TS + Tailwind + shadcn init
- [ ] 19. Zod schemas + TanStack Query client + typed API hooks
- [ ] 20. `AnalyzePage.tsx` — paste/upload + submit + polling
- [ ] 21. `ResultsPage.tsx` — 5-tab scroll-spy + result components

---

## Phase 4 — Observability (1 day)

- [ ] 22. Langfuse SDK in orchestrator + per-agent spans
- [ ] 23. `GET /traces/{run_id}` endpoint
- [ ] 24. `AgentTimeline.tsx` — live progress
- [ ] 25. `TraceViewer.tsx` — collapsible span tree

---

## Phase 5 — Evals (1 day)

- [ ] 26. `data/golden_cases.jsonl` — 15 labeled synthetic cases
- [ ] 27. `api/evals/ragas_runner.py`
- [ ] 28. `scripts/run_evals.sh` + assertion suite
- [ ] 29. `EvalDashboard.tsx`

---

## Phase 6 — Polish + ship (1 day)

- [ ] 30. README polish — Mermaid diagram, demo GIF, sample output
- [ ] 31. `docs/architecture.md`, `agent-design.md`, `evaluation.md`, `privacy.md`
- [ ] 32. GitHub Actions CI — Ruff + pytest + run_evals on PR
- [ ] 33. Demo GIF recording
- [ ] 34. `LICENSE` + push to public GitHub
