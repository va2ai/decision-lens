# Failure modes

What can go wrong, how the pipeline responds, and what the user sees.

## The taxonomy

| Class | Examples | Policy | User-visible result |
|---|---|---|---|
| Hard-abort | LLM unreachable during intake; Critic crash | Raise out of pipeline | HTTP 500, `run_id` returned for trace lookup |
| Soft-fail | Retrieval timeout; reasoning JSON-schema violation after retries; extraction span out-of-range | Mark context poisoned, continue | 200 with `AnalysisReport` carrying `pipeline_warnings[]`; all findings blocked by Critic |
| Quiet drop | LLM cites a source the retriever never returned | Reasoning post-filter drops the finding before the Critic sees it | 200, finding silently absent; counter increments in metadata |
| Schema bounce | Instructor validation fails on agent output | Instructor retries (configurable); on final failure → soft-fail or hard-abort per node | depends on node |
| Critic block | LLM critic returns `severity == "block"` for a grounded finding | Finding removed from `approved_finding_indices`, flag included in report | 200, finding visible in raw findings but absent from `approved`, with the explanatory flag |

## Hard-abort scenarios

### Intake fails

If the LLM cannot classify the document or normalize its text, downstream agents have nothing to work with. The exception bubbles out of `run_analysis_traced()` as HTTP 500. The `run_id` is still returned in the error response so the trace can be inspected.

**Mitigation in code:** none — failing loudly is correct. The intake prompt is intentionally short and the schema intentionally simple to minimize LLM-side failure surface.

### Critic fails

The Critic is the faithfulness gate. If it crashes, we cannot distinguish grounded findings from hallucinated ones. Letting the pipeline continue without it would silently regress the central correctness property of the system, so this is a hard-abort.

**Mitigation in code:** the deterministic guard runs first and does not depend on the LLM. If the LLM critic call fails, the deterministic guard's results are still applied — only the *additional* LLM-driven checks are lost. The `client=None` path is exercised by `tests/test_critic.py::test_hallucination_injection_is_flagged_without_llm`.

## Soft-fail scenarios

### Extraction span out-of-range

The Extraction agent returns `Issue.source_span = (start, end)` referencing character offsets in the input. `validate_spans()` drops any issue whose span falls outside the document. If *all* issues are dropped, the context is poisoned. If some survive, the surviving issues continue downstream.

### Retrieval returns nothing

If ChromaDB returns zero hits for every issue, `RetrievalOutput.references == []`. Reasoning then either produces zero findings (everything fails the schema's `min_length=1` citation requirement) or every finding gets dropped by the post-filter. Either way, the report shows the issues but no findings.

### Reasoning post-filter drops everything

If the LLM cites source ids that don't match any retrieved citation, the post-filter drops them. If every finding is dropped, the Critic still runs but has nothing to approve.

### LLM rate-limit or timeout

Caught by the per-node `try/except`. Soft-fail nodes mark `poisoned=True` and continue; hard-abort nodes raise.

## Quiet-drop scenarios (the most subtle)

### LLM cites a partially valid set of sources

A finding cites `[REG-3.310, REG-PHANTOM]`. The post-filter keeps `REG-3.310` and drops `REG-PHANTOM`. The finding survives with a narrower citation set.

The Critic then re-checks: if any remaining citation is still dangling, it blocks the finding entirely. If all remaining citations are grounded, the finding is approved.

This is intentional: a partially hallucinated citation list should not destroy a finding whose other citations are real, but the report should never carry a phantom id.

## Schema-bounce scenarios

Instructor retries on Pydantic validation failures, feeding the error back to the LLM as a structured message. On the final retry's failure:

- **Intake:** raised as hard-abort.
- **Extraction / Reasoning / Critic LLM stage:** raised inside the node's `try/except`, converted to soft-fail (extraction/reasoning) or hard-abort (critic).

## Critic-block scenarios

Even when citations are perfectly grounded, the LLM critic can flag a finding for other reasons:

- The finding's claim is broader than what the cited passage supports.
- The cited passage is on a related but distinct legal question.
- The finding's tone is recommendation-shaped where the cited authority is descriptive.

Block-severity flags drop the finding from `approved_finding_indices`. The full flag is preserved in the report so a reader can see *why* the finding was blocked.

## What the user sees

### Successful run

```json
{
  "run_id": "abc123",
  "report": {
    "summary": "...",
    "issues": [...],
    "findings": [...],
    "approved_finding_indices": [0, 1, 3],
    "critic_flags": [...],
    "pipeline_warnings": []
  }
}
```

### Soft-failed run

Same shape, but:

- `pipeline_warnings[]` is populated with structured entries naming the failed node.
- `approved_finding_indices` is empty.
- Every finding has a `block` flag attached.

The frontend renders these in the **Flags** tab so the user is not silently shown a degraded report.

### Hard-abort

HTTP 500 with `{ "detail": "<exception summary>", "run_id": "abc123" }`. The trace at `/traces/{run_id}` shows which span errored.

## Failure modes deliberately *not* handled

- **Token-budget overflow.** If the document is too long, the LLM call fails and the node's normal failure path kicks in. No internal chunking — the user is expected to bring documents of reasonable length, and the demo corpus is.
- **Adversarial prompt injection in the document text.** The model could in principle be steered by content embedded in the input. The Critic catches the most damaging outcome (a hallucinated citation), but prompt injection is not a primary threat model for this portfolio piece.
- **Embedding model drift.** ChromaDB caches the ONNX model locally; if the hosted model version changes upstream, existing collections may need re-indexing. Not addressed.

These are noted so a reviewer can see what's *not* claimed, not because they should be addressed before the next demo.
