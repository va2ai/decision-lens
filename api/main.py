"""FastAPI entry point — Phase 0 stub.

Returns a stubbed AnalysisReport so the schema contract is exercised end-to-end
before any agents are wired. Phase 1 replaces the stub with a real LangGraph run.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas.api import AnalysisRequest, AnalysisResponse
from api.schemas.pipeline import (
    AnalysisReport,
    AuthorityType,
    Citation,
    DocumentIssue,
    DocumentType,
    EvidenceItem,
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Phase 1+: warm provider client, load chroma collection, etc.
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
    """Phase 0 stub — returns a deterministic stubbed report.

    Confirms that the request and response schemas round-trip cleanly through
    the FastAPI layer. Phase 1 replaces the body of this function with a real
    pipeline invocation via api.agents.graph.run_analysis(req.raw_text).
    """
    if len(req.raw_text) < 50:
        raise HTTPException(status_code=400, detail="raw_text must be at least 50 chars")

    run_id = uuid4()
    stub = AnalysisReport(
        doc_type=DocumentType.UNKNOWN,
        generated_at=datetime.now(timezone.utc),
        overall_confidence=0.0,
        faithfulness_score=0.0,
        issues=[
            DocumentIssue(
                issue_text="(stub) pipeline not yet wired",
                decision="unclear",
                stated_reason=None,
                source_span=(0, min(len(req.raw_text), 100)),
                confidence=0.0,
            )
        ],
        evidence=[
            EvidenceItem(
                label="stub",
                description="Phase 0 — replace with real extraction in Phase 2.",
                source_type="missing",
                favorability="missing",
            )
        ],
        findings=[],
        strategy=[],
        citations=[
            Citation(
                source_id="STUB-001",
                title="Phase 0 placeholder",
                authority_type=AuthorityType.SECONDARY,
                passage="No real retrieval has run yet.",
            )
        ],
        critic_flags=[],
        pipeline_warnings=["Phase 0 stub — agents not yet wired."],
        prompt_version="stub:v0",
    )
    return AnalysisResponse(run_id=run_id, report=stub)
