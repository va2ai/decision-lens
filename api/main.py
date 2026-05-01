"""FastAPI entry point — wires the LangGraph pipeline behind POST /analyze."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.agents.graph import run_analysis_traced
from api.observability import get_trace_store
from api.retrieval.store import get_store
from api.schemas.api import AnalysisRequest, AnalysisResponse, TraceView


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Warm the retrieval store so the first request doesn't pay ingest cost.
    get_store().ensure_loaded()
    yield


app = FastAPI(
    title="decision-lens",
    description="Multi-agent document analysis pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest) -> AnalysisResponse:
    """Run the full 6-agent pipeline against the submitted document."""
    if len(req.raw_text) < 50:
        raise HTTPException(status_code=400, detail="raw_text must be at least 50 chars")
    try:
        report, trace = run_analysis_traced(req.raw_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"pipeline failure: {e}") from e
    return AnalysisResponse(run_id=trace.run_id, report=report)


@app.get("/traces/{run_id}", response_model=TraceView)
async def get_trace(run_id: str) -> TraceView:
    """Return the recorded span timeline for a recent pipeline run."""
    trace = get_trace_store().get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"unknown run_id: {run_id}")
    return TraceView.model_validate(trace.to_dict())


@app.get("/traces", response_model=list[TraceView])
async def list_traces(limit: int = 20) -> list[TraceView]:
    """List the most recent pipeline runs (in-memory ring buffer)."""
    return [
        TraceView.model_validate(t.to_dict()) for t in get_trace_store().list_recent(limit)
    ]
