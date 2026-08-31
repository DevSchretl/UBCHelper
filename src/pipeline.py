"""
Pipeline — the single adaptive entry point (Phase 4).

`answer()` is the one function the CLI, the API, and the eval all call. It routes each
question, then runs the matching path and returns a uniform result:

    router.classify(q)  ->  "simple"   retrieve + generate a grounded answer
                            "complex"  hand off to the agent (decompose -> multi-hop
                                       retrieve -> merge -> synthesize)

Returning {answer, results, route} keeps callers backend-agnostic: the CLI prints it, the
API serializes it, and the eval scores `results` (retrieval) and `answer` (generation).
"""

from __future__ import annotations

from . import agent, generate, retrieve, router, trace
from .retrieve import Result


def answer(
    question: str,
    top_k: int | None = None,
    mode: str | None = None,
    route: str | None = None,
) -> dict:
    """Route `question` and answer it. Pass `route` to force a path (skips classification)."""
    trace.step(f"PIPELINE - answer: {question!r}")
    route = route or router.classify(question)
    if route == "complex":
        results, ans = agent.run(question, top_k=top_k)
    else:
        trace.step("RETRIEVE - simple route (single query)")
        results = retrieve.retrieve(question, top_k=top_k, mode=mode)
        trace.step("GENERATE - grounded answer over the retrieved excerpts")
        ans = generate.generate_answer(question, results)
    trace.step(f"PIPELINE - done (route={route}, {len(results)} excerpts)")
    return {"answer": ans, "results": results, "route": route}


# Re-exported so callers can annotate/inspect results without importing retrieve directly.
__all__ = ["answer", "Result"]
