"""
Agent — the complex path of the adaptive pipeline (Phase 4), framework-free.

A plain Python loop, no LangChain/LangGraph, so the whole thing stays readable:

    decompose(question) -> sub-questions          one LLM call
    for each sub-question: retrieve.retrieve(...)  multi-hop recall
    round-robin merge + dedup the Result lists     each hop's best hit rises to the top
    synthesize(question, merged)                   one grounded answer over the union

The merge is what earns the complex path its keep: a single retrieval tends to satisfy one
part of a multi-hop question and starve the other, whereas retrieving each sub-question
separately and interleaving the rankings surfaces an excerpt for *every* hop — the recall
win the eval measures.

Synthesis deliberately reuses `generate.generate_answer`: the grounded SYSTEM_PROMPT and
`format_context` already turn a list of excerpts + the original question into one clean
answer, so there is nothing to reinvent here.
"""

from __future__ import annotations

from . import config, generate, retrieve, trace
from .retrieve import Result

DECOMPOSE_SYSTEM = (
    "You break a complex question about the UBC Academic Calendar into a few focused "
    "sub-questions, each of which can be answered from ONE calendar page (one course, "
    "one program's requirements, one policy). Cover every distinct course, program, "
    "student cohort, or side of a comparison the question asks about. Write one "
    "sub-question per line, no numbering, and produce at most {max_subq}. If the "
    "question is already single-focus, just restate it as the only line."
)


def decompose(question: str) -> list[str]:
    """Split `question` into up to AGENT_MAX_SUBQ sub-questions; fall back to the original."""
    trace.step("AGENT - decompose into sub-questions")
    system = DECOMPOSE_SYSTEM.format(max_subq=config.AGENT_MAX_SUBQ)
    reply = generate.complete(system, question)
    subqs = [_strip_bullet(line) for line in reply.splitlines()]
    subqs = [s for s in subqs if s]
    subqs = subqs[: config.AGENT_MAX_SUBQ] if subqs else [question]
    for i, sq in enumerate(subqs, start=1):
        trace.detail(f"sub-question {i}", sq)
    return subqs


def _strip_bullet(line: str) -> str:
    """Drop any leading list marker ("1.", "-", "*") the model may have added."""
    return line.strip().lstrip("0123456789.)-*• \t").strip()


def _merge(result_lists: list[list[Result]]) -> list[Result]:
    """Round-robin interleave per-sub-question results, deduped by chunk id (first wins).

    Taking rank-1 from every sub-question before any rank-2 keeps each hop's strongest hit
    near the top, which is exactly what recall@k on a multi-hop question rewards.
    """
    merged: list[Result] = []
    seen: set[int] = set()
    for rank in range(max((len(rl) for rl in result_lists), default=0)):
        for rl in result_lists:
            if rank < len(rl) and rl[rank].id not in seen:
                seen.add(rl[rank].id)
                merged.append(rl[rank])
    return merged


def synthesize(question: str, results: list[Result]) -> str:
    """Answer the original question grounded in the merged excerpts (capped for prompt size)."""
    return generate.generate_answer(question, results[: config.SYNTH_CONTEXT_K])


def run(question: str, top_k: int | None = None) -> tuple[list[Result], str]:
    """Decompose -> multi-hop retrieve -> merge -> synthesize. Returns (merged_results, answer).

    `top_k` sets how many excerpts to pull per sub-question (defaults to AGENT_SUBQ_TOP_K);
    the merged list can be longer, since it unions every hop.
    """
    per_hop = top_k or config.AGENT_SUBQ_TOP_K
    subqs = decompose(question)

    result_lists = []
    for i, sq in enumerate(subqs, start=1):
        trace.step(f"AGENT - multi-hop retrieve, sub-question {i}/{len(subqs)}: {sq!r}")
        result_lists.append(retrieve.retrieve(sq, top_k=per_hop))

    merged = _merge(result_lists)
    trace.step("AGENT - merge sub-question results (round-robin, dedup by chunk id)")
    trace.detail("merged excerpts", len(merged))
    trace.results(merged)

    trace.step("AGENT - synthesize final answer over the merged excerpts")
    answer = synthesize(question, merged)
    return merged, answer
