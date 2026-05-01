"""FastAPI entry point — wires the LangGraph pipeline behind POST /analyze."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.agents.graph import run_analysis
from api.retrieval.store import get_store
from api.schemas.api import AnalysisRequest, AnalysisResponse


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
        report = run_analysis(req.raw_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"pipeline failure: {e}") from e
    return AnalysisResponse(run_id=report.report_id, report=report)
