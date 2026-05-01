"""In-memory trace store + span context manager.

Records every agent invocation as a typed Span on the active Trace. The store is
process-local — a single FastAPI worker keeps a bounded ring buffer of recent runs.
For production you'd ship spans to Langfuse / OTel; this matches that data model
so swapping the sink is a one-file change.

If `langfuse` is installed AND `LANGFUSE_PUBLIC_KEY` is set, spans are also
forwarded to Langfuse. Otherwise the in-memory store is the sole sink.
"""

from __future__ import annotations

import os
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Any, Iterator, Literal


SpanStatus = Literal["ok", "error", "running"]


@dataclass
class Span:
    name: str
    started_at: float
    ended_at: float | None = None
    status: SpanStatus = "running"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        return round((self.ended_at - self.started_at) * 1000, 2)


@dataclass
class Trace:
    run_id: str
    started_at: float
    ended_at: float | None = None
    spans: list[Span] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        return round((self.ended_at - self.started_at) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_ms": self.duration_ms,
            "spans": [
                {**asdict(s), "duration_ms": s.duration_ms} for s in self.spans
            ],
        }


class TraceStore:
    """Bounded LRU cache of recent traces, keyed by run_id."""

    def __init__(self, max_traces: int = 256) -> None:
        self._traces: OrderedDict[str, Trace] = OrderedDict()
        self._max = max_traces
        self._lock = Lock()

    def start(self) -> Trace:
        run_id = uuid.uuid4().hex[:12]
        trace = Trace(run_id=run_id, started_at=time.time())
        with self._lock:
            self._traces[run_id] = trace
            if len(self._traces) > self._max:
                self._traces.popitem(last=False)
        return trace

    def end(self, trace: Trace) -> None:
        trace.ended_at = time.time()

    def get(self, run_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(run_id)

    def list_recent(self, limit: int = 20) -> list[Trace]:
        with self._lock:
            return list(reversed(list(self._traces.values())))[:limit]


_store_singleton: TraceStore | None = None


def get_trace_store() -> TraceStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = TraceStore()
    return _store_singleton


@contextmanager
def span(trace: Trace, name: str, **metadata: Any) -> Iterator[Span]:
    """Open a span on the trace; auto-closes with ok/error status.

    Usage:
        with span(trace, "intake", input_chars=len(text)) as s:
            result = run_intake(text)
            s.metadata["doc_type"] = result.doc_type.value
    """
    sp = Span(name=name, started_at=time.time(), metadata=dict(metadata))
    trace.spans.append(sp)
    try:
        yield sp
        sp.status = "ok"
    except Exception as exc:  # noqa: BLE001
        sp.status = "error"
        sp.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        sp.ended_at = time.time()
        _maybe_forward_to_langfuse(trace, sp)


# --- Optional Langfuse passthrough ---------------------------------------------

_langfuse_client: Any | None = None
_langfuse_checked: bool = False


def _maybe_forward_to_langfuse(trace: Trace, sp: Span) -> None:
    """Best-effort forward; never raises into the calling pipeline."""
    global _langfuse_client, _langfuse_checked
    if not _langfuse_checked:
        _langfuse_checked = True
        if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
            return
        try:
            from langfuse import Langfuse  # type: ignore

            _langfuse_client = Langfuse()
        except Exception:  # noqa: BLE001
            _langfuse_client = None
    if _langfuse_client is None:
        return
    try:
        _langfuse_client.trace(  # type: ignore[union-attr]
            id=trace.run_id,
            name="decision-lens",
            metadata={"span": sp.name, **sp.metadata},
        )
    except Exception:  # noqa: BLE001
        pass
