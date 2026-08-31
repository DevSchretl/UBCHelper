"""
Router — the "adaptive" in adaptive RAG (Phase 4).

One small function decides how much machinery a question deserves:

    simple   a single fact or page lookup       -> the fast Phase-2 retriever
    complex  needs several pages, a              -> the agentic loop (decompose ->
             comparison, or multi-step reasoning    multi-hop retrieve -> synthesize)

The classification is a cheap zero-shot LLM call reusing the generation backend, so there
is no extra model to configure. Anything the model returns other than a clear "complex"
falls back to "simple" — the cheaper path is the safe default, so a misparse never sends a
simple question down the expensive agent.
"""

from __future__ import annotations

from . import generate, trace

CLASSIFY_SYSTEM = (
    "You are a query router for a UBC academic-calendar Q&A system. Classify the user's "
    "question as either 'simple' or 'complex'.\n"
    "  simple  — answerable from one calendar page (a single course's prerequisites or "
    "description, one program's requirements, one policy or date).\n"
    "  complex — needs multiple courses or programs, a comparison (between programs, "
    "student cohorts, or calendar editions), or a prerequisite/requirement chain "
    "(e.g. 'compare X and Y', or 'what do I need to take before Z').\n"
    "Reply with exactly one word: simple or complex."
)


def classify(question: str) -> str:
    """Return "simple" or "complex" for `question`. Defaults to "simple" on any surprise."""
    trace.step("ROUTE - classify (simple vs complex)")
    reply = generate.complete(CLASSIFY_SYSTEM, question).strip().lower()
    route = "complex" if "complex" in reply else "simple"
    trace.detail("decision", route)
    return route
